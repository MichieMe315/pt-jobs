PRINTABLE_FILES = frozenset({'exercise-tracker.pdf', 'appointment-notes.pdf', 'practice-planner-2027.pdf'})
PALETTES = ('grayscale', 'plum')


def variants(download):
    name = getattr(download, 'name', '')
    if name not in {f'bundled/{file}' for file in PRINTABLE_FILES}:
        return {}
    return {key: name.removesuffix('.pdf') + f'-{key}.pdf' for key in PALETTES}
