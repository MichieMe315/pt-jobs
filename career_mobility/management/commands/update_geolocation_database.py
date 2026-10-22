import gzip
import hashlib
import os
import re
import tempfile
from datetime import date
from pathlib import Path
from urllib.request import Request,urlopen
from django.core.management.base import BaseCommand, CommandError
from career_mobility.geolocation import DATABASE, _reader

class Command(BaseCommand):
    help='Update the local DB-IP Lite country database; no visitor data is sent.'
    def add_arguments(self,parser):
        parser.add_argument('--month',default=date.today().strftime('%Y-%m'))
    def handle(self,*args,**options):
        month=options['month']
        if not re.fullmatch(r'20\d{2}-(0[1-9]|1[0-2])',month):raise CommandError('Use YYYY-MM.')
        import maxminddb
        from django.conf import settings
        target=Path(getattr(settings,'PTJC_GEOIP_DATABASE',DATABASE))
        url=f'https://download.db-ip.com/free/dbip-country-lite-{month}.mmdb.gz'
        try:
            with urlopen(Request(url,headers={'User-Agent':'PTJC country database updater'}),timeout=40) as response:
                compressed=response.read(30*1024*1024+1)
            if len(compressed)>30*1024*1024:raise ValueError('Unexpected database size')
            data=gzip.decompress(compressed)
            if len(data)>60*1024*1024:raise ValueError('Unexpected database size')
            target.parent.mkdir(parents=True,exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=target.parent,suffix='.mmdb',delete=False) as temp:
                temp.write(data);name=temp.name
            try:
                with maxminddb.open_database(name) as db:
                    record=db.get('8.8.8.8')
                    if not record or not record.get('country'):raise ValueError('Invalid country database')
                os.replace(name,target);_reader.cache_clear()
            finally:
                if os.path.exists(name):os.unlink(name)
        except Exception as exc:
            raise CommandError('Country database update failed; existing database retained.') from exc
        self.stdout.write(self.style.SUCCESS(f'DB-IP country database updated to {month}; SHA256 {hashlib.sha256(data).hexdigest()}. Attribution: https://db-ip.com (CC BY 4.0).'))
