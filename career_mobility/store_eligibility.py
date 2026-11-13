ACCOUNTS = (('employer', 'Employer'), ('jobseeker', 'Job Seeker'), ('international', 'International'))


def account_type(user):
    if not getattr(user, 'is_active', False):
        return None
    international = getattr(user, 'international_pt_profile', None)
    if international:
        return 'international'
    profile = getattr(user, 'jobseeker', None)
    if profile and profile.is_approved and profile.login_active:
        return 'jobseeker'
    if getattr(user, 'employer', None):
        return 'employer'
    return None


def account_requirement(user, product):
    from ptjc_resumes.offers import resume_template_for
    role = account_type(user)
    if product.eligible_accounts and role not in product.eligible_accounts:
        return "This product is unavailable for your account type."
    if role == 'employer' and (product.includes_resume_builder or 'resume' in product.slug or product.kind == 'workbook'):
        return "This product is available to candidates only."
    if role and product.audience != 'both' and (role == 'international') != (product.audience == 'international'):
        return "This product belongs to a different storefront."
    template = resume_template_for(product) if product.includes_resume_builder else None
    if template and template.key == 'canadian-professional':
        profile = getattr(user, 'jobseeker', None)
        if not profile or not profile.is_approved or not profile.login_active:
            return 'An approved Canadian job seeker account is required for this resource.'
    elif product.includes_card_builder:
        if role not in ('employer', 'jobseeker', 'international'):
            return 'A supported account is required to purchase business card access.'
    elif product.is_online_builder or product.kind == 'workbook':
        if not hasattr(user, 'international_pt_profile'):
            return 'An international planning account is required for this resource.'
    return ''
