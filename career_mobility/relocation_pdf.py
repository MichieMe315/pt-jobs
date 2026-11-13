from django.views.decorators.http import require_POST
from django.http import HttpResponse

@require_POST
def relocation_comparison_pdf(request):
    """Recalculate a submitted Canadian city comparison; never trust client totals."""
    import json
    from django.http import JsonResponse
    try:data=json.loads(request.body)
    except (ValueError,TypeError):return JsonResponse({'error':'Invalid comparison.'},status=400)
    return comparison_response(data)


def comparison_response(data):
    """The same report for a downloaded comparison and an owned saved plan."""
    import json
    from decimal import Decimal, InvalidOperation
    from io import BytesIO
    from xml.sax.saxutils import escape
    from django.http import JsonResponse
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    try:
        if not isinstance(data, dict):
            raise ValueError("Invalid input")
        origin = str(data.get("origin", "")).strip()[:100]
        destination = str(data.get("destination", "")).strip()[:100]
        if not origin or not destination or origin.casefold() == destination.casefold():
            raise ValueError("Select two different locations")
        def amount(key, required=False):
            raw = data.get(key, "")
            if raw in (None, ""):
                if required: raise ValueError(key)
                return Decimal("0")
            try: value = Decimal(str(raw))
            except (InvalidOperation, ValueError, TypeError): raise ValueError(key)
            if not value.is_finite() or value < 0 or value > 100000000:
                raise ValueError(key)
            return value
        required = ("current-salary", "new-salary", "current-rent", "new-rent")
        values = {key: amount(key, True) for key in required}
        for key in ("current-living", "new-living", "moving", "licensing", "one-time", "current-net", "new-net"):
            values[key] = amount(key)
        mode = data.get("expense_mode", "total")
        if mode not in ("total", "itemized"): raise ValueError("expense_mode")
        if mode == "itemized":
            for side in ("current", "new"):
                values[side+"-living"] = sum((amount(side+"-"+k) for k in ("utilities", "transport", "groceries", "childcare", "extra")), Decimal("0"))
        net_current, net_new = data.get("current-net"), data.get("new-net")
        has_current=net_current is not None and str(net_current).strip()!=''
        has_new=net_new is not None and str(net_new).strip()!=''
        if has_current != has_new:
            raise ValueError("Both take-home figures must be entered")
        takehome = has_current and has_new
        a = values["current-net"] if takehome else values["current-salary"]/12
        b = values["new-net"] if takehome else values["new-salary"]/12
        current_cost = values["current-rent"] + values["current-living"]
        new_cost = values["new-rent"] + values["new-living"]
        delta = (b-new_cost)-(a-current_cost)
        upfront = sum((values[k] for k in ("moving", "licensing", "one-time")), Decimal("0"))
    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse({"error": "Enter two different cities and valid financial figures."}, status=400)
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, title="PTJC Canadian relocation cost comparison", leftMargin=42, rightMargin=42)
    styles = getSampleStyleSheet()
    story = [Paragraph("Canadian relocation cost comparison", styles["Title"]), Spacer(1, 12),
             Paragraph(escape(origin)+" to "+escape(destination), styles["Heading2"]), Spacer(1, 16)]
    fmt=lambda n: "CAD ${:,.2f}".format(n)
    rows = [["Comparison", "Current", "Destination"],
            ["Annual gross salary", fmt(values["current-salary"]), fmt(values["new-salary"])],
            ["Monthly housing", fmt(values["current-rent"]), fmt(values["new-rent"])],
            ["Other monthly living costs", fmt(values["current-living"]), fmt(values["new-living"])],
            ["Monthly income basis", fmt(a), fmt(b)],
            ["Monthly amount after costs", fmt(a-current_cost), fmt(b-new_cost)]]
    table=Table(rows, colWidths=[200,150,150], repeatRows=1)
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#b62c3a')),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f1f3f5')]),
        ('BOTTOMPADDING',(0,0),(-1,-1),10),('TOPPADDING',(0,0),(-1,-1),10)]))
    story.extend([table, Spacer(1, 18), Paragraph("Monthly difference: "+fmt(delta),styles["Heading2"]),
        Paragraph("Annual difference: "+fmt(delta*12),styles["Normal"]),
        Paragraph("One-time relocation costs: "+fmt(upfront),styles["Normal"]),
        Paragraph("First-year difference after relocation costs: "+fmt(delta*12-upfront),styles["Normal"]),
        Paragraph("Three-year difference after relocation costs: "+fmt(delta*36-upfront),styles["Normal"]),
        Spacer(1,20),Paragraph("Method: "+("user-entered monthly take-home pay" if takehome else "gross annual pay divided by twelve")+". Figures are supplied by the user; no regional cost estimates have been inferred.",styles["Normal"]),
        Spacer(1,10),Paragraph("Gross comparisons do not deduct income tax or payroll deductions. Verify housing, salary and moving costs before making a decision.",styles["Italic"])])
    doc.build(story)
    response=HttpResponse(buffer.getvalue(),content_type="application/pdf")
    response["Content-Disposition"]='attachment; filename="ptjc-relocation-comparison.pdf"'
    response["Cache-Control"]="private, no-store"
    return response
