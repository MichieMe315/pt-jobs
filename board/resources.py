from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from django.contrib.auth.models import User
from django.utils.dateparse import parse_date
from decimal import Decimal, InvalidOperation
from . import models as m

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

TRUE_SET = {"1", "true", "y", "yes"}
FALSE_SET = {"0", "false", "n", "no"}

def as_bool(val, default=False):
    s = str(val or "").strip().lower()
    if s in TRUE_SET:
        return True
    if s in FALSE_SET:
        return False
    return default

def as_decimal(val):
    if val is None or str(val).strip() == "":
        return None
    try:
        return Decimal(str(val).replace(",", "").strip())
    except (InvalidOperation, ValueError):
        return None

def as_int(val, default=0):
    try:
        return int(str(val).replace(",", "").strip())
    except Exception:
        return default

def first(*vals):
    for v in vals:
        if str(v or "").strip() != "":
            return v
    return ""

def norm_choice(value, mapping, default=None):
    s = str(value or "").strip().lower()
    return mapping.get(s, default)

def split_full_name(full):
    s = (full or "").strip()
    if not s:
        return "", ""
    parts = [p for p in s.split() if p.strip()]
    if len(parts) == 1:
        return parts[0], ""
    return " ".join(parts[:-1]), parts[-1]

def first_nonblank_key(row, *keys):
    for k in keys:
        if k in row and str(row[k]).strip() != "":
            return k
    return None

# ------------------------------------------------------------
# Employer import/export (flex headers)
# ------------------------------------------------------------

EMPLOYER_ALIASES = {
    "user_username": ["user", "username", "user name", "user_name", "account_username"],
    "email": ["employer email", "email address", "e-mail", "mail"],
    "name": ["full name", "contact", "contact name", "contact person", "name (contact)"],
    "company_name": ["company", "employer", "organization", "clinic", "business", "company name"],
    "phone": ["phone number", "telephone", "tel", "mobile", "cell"],
    "website": ["website url", "site", "url", "homepage", "web"],
    "location": ["location", "city", "city/province", "city - province", "province", "region", "address"],
    "description": ["about", "bio", "notes", "summary", "details"],
    "is_approved": ["approved", "status", "is approved"],
    "posting_package__code": ["package", "package code", "plan", "product", "product code"],
    "credits_total": ["credits", "credit total", "total credits", "available credits"],
    "credits_used": ["used credits", "credits used"],
}

class EmployerResource(resources.ModelResource):
    user = fields.Field(
        column_name="user_username",
        attribute="user",
        widget=ForeignKeyWidget(User, "username"),
    )
    credits_left = fields.Field(attribute="credits_left", column_name="credits_left", readonly=True)

    class Meta:
        model = m.Employer
        import_id_fields = ["email"]
        fields = (
            "user",
            "email",
            "name",
            "company_name",
            "phone",
            "website",
            "location",
            "description",
            "is_approved",
            "posting_package__code",
            "credits_total",
            "credits_used",
            "credits_left",
        )
        export_order = fields

    def before_import_row(self, row, **kwargs):
        # Remap flexible headers → expected keys
        lower_map = {k.lower().strip(): k for k in row.keys()}
        for target, alts in EMPLOYER_ALIASES.items():
            if target not in row or str(row.get(target, "")).strip() == "":
                # direct lowercase key
                if target.lower() in lower_map:
                    row[target] = row.get(lower_map[target.lower()], "")
                    continue
                # alias lookup
                for alt in alts:
                    if alt.lower() in lower_map:
                        row[target] = row.get(lower_map[alt.lower()], "")
                        break

        # Normalize booleans and ints
        row["is_approved"] = as_bool(row.get("is_approved"), default=True)
        row["credits_total"] = as_int(row.get("credits_total"), default=0)
        row["credits_used"] = as_int(row.get("credits_used"), default=0)

# ------------------------------------------------------------
# JobSeeker import/export (flex headers)
# ------------------------------------------------------------

JOBSEEKER_ALIASES = {
    "user_username": ["user", "username", "user name", "user_name", "account_username"],
    "email": ["email", "email address", "e-mail", "mail"],
    "first_name": ["first name", "firstname", "given name"],
    "last_name": ["last name", "lastname", "surname", "family name"],
    "full_name": ["full name", "name"],
    "registration_status": [
        "registered status",
        "registration",
        "are you a registered professional in canada",
        "reg status",
        "registered in canada",
    ],
    "opportunity_type": ["opportunity type", "job type", "interested in", "type of opportunity"],
    "current_location": ["current location", "city", "city/province", "location"],
    "open_to_relocation": ["open to relocating", "open to relocation", "relocation open"],
    "relocation_where": ["relocation where", "if yes where", "preferred relocation"],
    "need_sponsorship": ["need sponsorship", "require sponsorship"],
    "seeking_immigration": ["seeking immigration", "immigration"],
    # legacy / optional
    "city": ["legacy city"],
    "province": ["legacy province"],
    "position_desired": ["position desired", "desired position"],
    "is_registered_canada": ["is registered canada"],
    "is_approved": ["approved", "status", "is approved"],
    "created_at": ["created at", "created"],
}

REG_STATUS_MAP = {
    "yes": "yes",
    "no": "no",
    "canadian new grad": "new_grad",
    "new grad": "new_grad",
    "credentialed": "credentialed",
    "completed credentialing": "credentialed",
    "completed written pce": "pce_written",
    "pce written": "pce_written",
}

JOB_TYPE_MAP = {
    "full-time": "full_time",
    "full time": "full_time",
    "fulltime": "full_time",
    "part-time": "part_time",
    "part time": "part_time",
    "parttime": "part_time",
    "contractor": "contractor",
    "resident": "resident",
    "intern": "intern",
    "locum": "locum",
}

class JobSeekerResource(resources.ModelResource):
    user = fields.Field(
        column_name="user_username",
        attribute="user",
        widget=ForeignKeyWidget(User, "username"),
    )
    full_name = fields.Field(attribute="full_name", column_name="full_name", readonly=True)

    class Meta:
        model = m.JobSeeker
        import_id_fields = ["email"]
        fields = (
            "user",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "registration_status",
            "opportunity_type",
            "current_location",
            "open_to_relocation",
            "relocation_where",
            "need_sponsorship",
            "seeking_immigration",
            "city",
            "province",
            "position_desired",
            "is_registered_canada",
            "is_approved",
            "created_at",
        )
        export_order = fields

    def before_import_row(self, row, **kwargs):
        # Remap headers
        lower_map = {k.lower().strip(): k for k in row.keys()}
        for target, alts in JOBSEEKER_ALIASES.items():
            if target not in row or str(row.get(target, "")).strip() == "":
                if target.lower() in lower_map:
                    row[target] = row.get(lower_map[target.lower()], "")
                    continue
                for alt in alts:
                    if alt.lower() in lower_map:
                        row[target] = row.get(lower_map[alt.lower()], "")
                        break

        # If only full_name present, split
        if (not row.get("first_name") and not row.get("last_name")) and row.get("full_name"):
            fn, ln = split_full_name(row.get("full_name"))
            row["first_name"], row["last_name"] = fn, ln

        # Normalize choices + booleans
        row["registration_status"] = norm_choice(row.get("registration_status"), REG_STATUS_MAP, default="no")
        row["opportunity_type"] = norm_choice(row.get("opportunity_type"), JOB_TYPE_MAP, default=None)
        row["open_to_relocation"] = as_bool(row.get("open_to_relocation"))
        row["need_sponsorship"] = as_bool(row.get("need_sponsorship"))
        row["seeking_immigration"] = as_bool(row.get("seeking_immigration"))
        row["is_registered_canada"] = as_bool(row.get("is_registered_canada"))
        row["is_approved"] = as_bool(row.get("is_approved"))
        # created_at may be left blank; import-export will handle if field missing

# ------------------------------------------------------------
# Job import/export (flex headers)
# ------------------------------------------------------------

JOB_ALIASES = {
    "id": ["id", "job id"],
    "employer_email": ["employer email", "employer", "employer contact email"],
    "title": ["job title", "title"],
    "description": ["job description", "description", "details"],
    "location": ["location", "city", "city/province"],
    "compensation_type": ["compensation type", "salary type", "pay type"],
    "salary_min": ["salary min", "min salary", "min pay"],
    "salary_max": ["salary max", "max salary", "max pay"],
    "percent_split": ["percent split", "% split", "split %"],
    "job_type": ["job type", "type"],
    "relocation_assistance": ["relocation assistance", "relocation", "is relocation assistance provided"],
    "posting_date": ["posting date", "posted", "date posted"],
    "expiry_date": ["expiry date", "expires", "date expires"],
    "featured": ["featured"],
    "is_active": ["active", "is active", "status"],
    "application_email": ["application email", "apply email", "apply via email"],
    "external_apply_url": ["apply url", "application url", "external apply url", "apply link"],
}

COMP_MAP = {
    "hourly": "hourly",
    "yearly": "yearly",
    "% split": "percent",
    "percent": "percent",
    "percentage": "percent",
    "split": "percent",
}

class JobResource(resources.ModelResource):
    employer = fields.Field(
        column_name="employer_email",
        attribute="employer",
        widget=ForeignKeyWidget(m.Employer, "email"),
    )

    class Meta:
        model = m.Job
        import_id_fields = ["id"]  # allow updates if id present
        fields = (
            "id",
            "employer",
            "title",
            "description",
            "location",
            "compensation_type",
            "salary_min",
            "salary_max",
            "percent_split",
            "job_type",
            "relocation_assistance",
            "posting_date",
            "expiry_date",
            "featured",
            "is_active",
            "application_email",
            "external_apply_url",
            "view_count",
            "application_count",
        )
        export_order = fields

    def before_import_row(self, row, **kwargs):
        # Remap headers
        lower_map = {k.lower().strip(): k for k in row.keys()}
        for target, alts in JOB_ALIASES.items():
            if target not in row or str(row.get(target, "")).strip() == "":
                if target.lower() in lower_map:
                    row[target] = row.get(lower_map[target.lower()], "")
                    continue
                for alt in alts:
                    if alt.lower() in lower_map:
                        row[target] = row.get(lower_map[alt.lower()], "")
                        break

        # Normalize compensation & salary fields
        row["compensation_type"] = norm_choice(row.get("compensation_type"), COMP_MAP, default="hourly")
        row["salary_min"] = as_decimal(row.get("salary_min"))
        row["salary_max"] = as_decimal(row.get("salary_max"))
        row["percent_split"] = as_int(row.get("percent_split"), default=None)

        # Job type
        row["job_type"] = norm_choice(row.get("job_type"), JOB_TYPE_MAP, default=None)

        # Booleans
        row["relocation_assistance"] = as_bool(row.get("relocation_assistance"))
        row["featured"] = as_bool(row.get("featured"))
        row["is_active"] = as_bool(row.get("is_active"), default=True)

        # Dates
        for key in ("posting_date", "expiry_date"):
            val = row.get(key)
            if val and not isinstance(val, str):
                # import-export sometimes passes date objects already
                continue
            if val:
                d = parse_date(str(val))
                row[key] = d.isoformat() if d else None

        # counts (optional)
        row["view_count"] = as_int(row.get("view_count"), default=0)
        row["application_count"] = as_int(row.get("application_count"), default=0)
