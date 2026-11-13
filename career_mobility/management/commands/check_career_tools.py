"""Read-only release checks; never changes accounts, keys or product settings."""
from getpass import getpass
import os
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from django.core.management.base import BaseCommand,CommandError
from django.urls import reverse,NoReverseMatch
from career_mobility.store_config import stripe_key,webhook_secret
from career_mobility.models import DigitalProduct
from ptjc_resumes.models import ResumeTemplate

class Command(BaseCommand):
    help='Check career-tool release readiness. --admin-login verifies a local login without resetting or creating an account.'
    def add_arguments(self,parser):
        parser.add_argument('--admin-login',action='store_true')
        parser.add_argument('--strict',action='store_true',help='Exit with an error when paid-launch checks are incomplete.')
    def handle(self,*args,**options):
        issues=[]
        def report(label,ok,problem):
            self.stdout.write(label+': '+('OK' if ok else 'NOT READY'))
            if not ok:issues.append(problem)
        db=settings.DATABASES['default'];engine=db['ENGINE'].rsplit('.',1)[-1]
        self.stdout.write('Database: '+engine+' · '+str(db['NAME']))
        sha=os.environ.get('RAILWAY_GIT_COMMIT_SHA','')
        if sha:self.stdout.write('Deployed commit: '+sha[:12])
        self.stdout.write('DEBUG: '+str(settings.DEBUG))
        User=get_user_model();staff=User.objects.filter(is_staff=True,is_active=True)
        self.stdout.write('Active admin-capable accounts: '+str(staff.count()))
        self.stdout.write('Active superusers: '+str(staff.filter(is_superuser=True).count()))
        can_manage=any(user.has_perms(['career_mobility.view_digitalproduct','career_mobility.change_digitalproduct','career_mobility.view_productorder']) for user in staff)
        report('Admin can manage the digital shop',can_manage,'No active staff account has the required digital-shop permissions. No permissions were changed.')
        if not staff.exists():issues.append('No active staff account exists in this database. No accounts were created or modified by this command.')
        if settings.DEBUG and settings.SESSION_COOKIE_SECURE:issues.append('Secure session cookies are enabled. They will not work with a plain HTTP localhost login.')
        if settings.DEBUG and settings.CSRF_COOKIE_SECURE:issues.append('Secure CSRF cookies are enabled. They will not work with plain HTTP localhost forms.')
        report('Stripe API key configured',bool(stripe_key()),'The current process cannot find a Stripe API key. Production and local settings are separate.')
        report('Digital webhook secret configured',bool(webhook_secret()),'The current process cannot find PT_MOBILITY_STRIPE_WEBHOOK_SECRET.')
        try:
            path=reverse('mobility_stripe_webhook');self.stdout.write('Digital webhook route: '+path)
        except NoReverseMatch:issues.append('The digital webhook route is unavailable.')
        try:reverse('mobility_product_checkout',args=[0])
        except NoReverseMatch:issues.append('New digital purchases are disabled in this process.')
        workbook=DigitalProduct.objects.filter(slug='international-planning-workbook',kind='workbook').first()
        report('Workbook product',bool(workbook and workbook.is_published),'Run the supplied migrations and confirm the workbook product is published.')
        if workbook:self.stdout.write('Workbook price: CAD '+str(workbook.price_cad))
        template=ResumeTemplate.objects.select_related('access_product').filter(key='international-professional').first()
        report('Resume template enabled',bool(template and template.is_enabled),'Enable the intended resume template in admin after reviewing it.')
        product=template.access_product if template else None
        report('Resume access product published',bool(product and product.is_published),'Set the intended resume price and publication status in admin.')
        if product:self.stdout.write('Resume access price: CAD '+str(product.price_cad))
        card=DigitalProduct.objects.filter(slug='international-business-card-builder-access').first()
        self.stdout.write('Business-card product: '+('Published at CAD '+str(card.price_cad) if card and card.is_published else 'Unpublished; no card sales enabled'))
        from django.contrib.staticfiles import finders
        # A linked editor requires no uploaded file. Bundles require every
        # downloadable item to be ready, including items not sold separately.
        from career_mobility.store_access import snapshot
        bad_products = []
        for listing in DigitalProduct.objects.filter(is_published=True).order_by('slug'):
            try:
                rows = snapshot(listing)
                items = DigitalProduct.objects.in_bulk(row['product_id'] for row in rows)
                for row in rows:
                    item = items[row['product_id']]
                    if item.kind == 'file' and not item.is_online_builder and (
                        not item.download or not item.download.storage.exists(item.download.name)
                    ):
                        raise ValueError('missing file')
                if listing.preview_image and not listing.preview_image.storage.exists(listing.preview_image.name):
                    raise ValueError('missing cover')
            except (ValueError, OSError, KeyError):
                bad_products.append(listing.slug)
        report('Published product files', not bad_products,
               'Review missing files, covers or empty bundles: ' + ', '.join(bad_products))
        assets = ('board/marketing/brand-logo.png', 'board/ptjc-operations.css',
                  'career_mobility/digital-shop.css', 'career_mobility/planner.css',
                  *(f'ptjc_resumes/designs/{design}.png' for design in ('classic','clinical','editorial','sidebar',
                      'canadian-classic','canadian-clinical','canadian-editorial','canadian-sidebar')))
        missing = [asset for asset in assets if not finders.find(asset)]
        report('Admin, storefront and résumé preview assets', not missing,
               'Restore missing static files: ' + ', '.join(missing))
        if options['admin_login']:self.check_login(User)
        if issues:
            self.stdout.write('\nOutstanding setup:')
            for item in issues:self.stdout.write('- '+item)
        self.stdout.write('\nPaid-launch configuration: '+('NOT READY' if issues else 'Present; live payment and webhook delivery still require verification.'))
        self.stdout.write('This check changed no accounts, passwords, credentials or product settings.')
        if options['strict'] and issues:raise CommandError('Complete the reported setup before a paid launch.')
    def check_login(self,User):
        identifier=input('Admin username (or unique email): ').strip()
        field=User.USERNAME_FIELD;user=User.objects.filter(**{field:identifier}).first()
        if user is None and identifier:
            matches=User.objects.filter(email__iexact=identifier)
            if matches.count()==1:user=matches.first()
        if user is None:raise CommandError('No unique matching user in this database. Nothing was reset or created.')
        if not user.is_active:raise CommandError('This account is inactive. No permissions were changed.')
        if not user.is_staff:raise CommandError('This account does not have staff access. No permissions were changed.')
        if not user.has_usable_password():raise CommandError('This account has no usable password. No password was changed.')
        password=getpass('Password (hidden; never printed or saved): ')
        verified=check_password(password,user.password)
        if not verified:raise CommandError('The supplied password was not accepted. No password was changed.')
        self.stdout.write('Admin credentials accepted for username: '+str(getattr(user,field)))
