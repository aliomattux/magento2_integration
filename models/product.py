from odoo import api, fields, models, SUPERUSER_ID, _, exceptions
from datetime import datetime, timedelta

class Product(models.Model):
    _inherit = 'product'


    def prepare_odoo_record_vals(self, job, record):
        base_url = job.mage_instance.url
        media_ext = 'media/catalog/product'
        img_url = base_url + media_ext

        image_path = record.get('thumbnail')
        if not image_path:
            image_path = record.get('small_image')

        if image_path:
            image_path = img_url + image_path

        vals = {
                'img_path': image_path,
                'upc': record.get('upc'),
                'url_key': record.get('url_key'),
                'name': record.get('name') or record.get('sku'),
                'mage_name': record.get('name'),
                'sku': record['sku'],
                'mage_type': record['type_id'],
                'entity_id': record['entity_id'],
                'mage_last_sync_date': datetime.utcnow(),
                'short_description': record.get('short_description', ''),
                'sync_to_mage': True,
                'mage_status': str(record.get('status')),
        }

        return vals


    def upsert_mage_record(self, vals, record_id=False):
        if record_id:
            record = self.browse(record_id)
            record.write(vals)
            return record_id

        products = self.search([('entity_id', '=', vals['entity_id'])])
        if products:
            product = products[0]
            if product.sku != vals.get('sku'):
                vals['internalid'] = None

            product.write(vals)
            return product

        if not products:
            query = "SELECT id FROM product WHERE LOWER(sku) = LOWER('%s')"%vals['sku']
            self.env.cr.execute(query)
            res = self.env.cr.dictfetchall()
            if not res:
                return self.create(vals)

            id = res[0]['id']
            product = self.browse(id)
            product.write(vals)
            return product
