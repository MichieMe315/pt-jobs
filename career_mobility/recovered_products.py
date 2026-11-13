PRODUCTS = (
 ('appointment-card-designs','Appointment Card Designs','Practice stationery','both','Three appointment card backs in SVG, PNG and print PDF.','05-Practice-Designs/Appointment-Cards/'),
 ('practice-postcards','Practice Postcards','Practice stationery','both','Four double-sided postcard designs in editable SVG and print formats.','05-Practice-Designs/Postcards/'),
 ('practice-prints','Physiotherapy Practice Prints','Practice stationery','both','Four printable designs: Hands, Joint, Motion and Movement.','05-Practice-Designs/Practice-Prints/'),
 ('practice-brand-assets','Practice Brand Assets','Practice stationery','both','Six SVG monograms and banners in three colourways.','05-Practice-Designs/Brand-Assets/'),
 ('business-card-design-files','Business Card Design Files','Practice stationery','both','Four double-sided business card designs for offline editing.','05-Practice-Designs/Business-Cards/'),
 ('candidate-interview-workbook','Candidate Interview Workbook','Career workbooks','both','Editable Word workbook and print PDF for interview preparation.','02-Career-Tools/Candidate-Interview-Workbook.'),
 ('career-workbook-files','Career Workbook Files','Career workbooks','both','Word and PDF tools for an achievement portfolio, résumé writing and offer review.','02-Career-Tools/'),
 ('international-workbook-files','International Planning Workbook Set','International planning','international','Four Word and PDF workbooks for documents, budgeting, exam preparation and route planning.','03-International-Planning/'),
 ('planning-spreadsheet','PTJC Planning Spreadsheet','Career workbooks','both','Excel planning workbook for tracking career milestones.','06-Trackers/PTJC-Planning-Workbook.xlsx'),
)
FILES = {key: key+('.xlsx' if key=='planning-spreadsheet' else '.zip') for key,*_ in PRODUCTS}

CARD_DESIGN_FILES = {
    'clinical': ('Clinical', 'Clinical-Business'),
    'community': ('Community', 'Community-Business'),
    'editorial': ('Editorial', 'Editorial-Business'),
    'networking': ('International Networking', 'International-Networking'),
}


def card_design_archive(source, design):
    """Extract one complete design without rewriting or exposing other members."""
    from io import BytesIO
    from pathlib import PurePosixPath
    from zipfile import BadZipFile, ZIP_DEFLATED, ZipFile

    try:
        prefix = CARD_DESIGN_FILES[design][1]
        output = BytesIO()
        with ZipFile(source) as original, ZipFile(output, 'w', ZIP_DEFLATED) as selected:
            total = 0
            seen = set()
            for info in original.infolist():
                name = PurePosixPath(info.filename).name
                if info.is_dir() or not name.startswith(prefix + '-') or name in seen:
                    continue
                total += info.file_size
                if total > 15_000_000:
                    raise ValueError('Card files are too large.')
                selected.writestr(name, original.read(info))
                seen.add(name)
            if not seen:
                raise ValueError('No files for that design.')
        output.seek(0)
        return output
    except (KeyError, BadZipFile, OSError) as exc:
        raise ValueError('Card files are unavailable.') from exc
