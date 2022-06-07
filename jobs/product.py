from odoo import api, fields, models, SUPERUSER_ID, _
from datetime import datetime, timedelta
import logging
_logger = logging.getLogger(__name__)

class MageIntegrator(models.TransientModel):

    _inherit = 'mage.integrator'

    def import_all_rest_products(self, job):
        #Main for M2
        #product must be simple and enabled
        url = '/products?'
        filters = [
        {
            'field': 'status',
            'value': '1',
            'condition_type': 'eq',
        },
        {
            'field': 'type_id',
            'value': 'simple',
            'condition_type': 'eq',
        }]

        filters = self.get_rest_filters(filters)
        url += filters
        current_page = 1
        page_size = 400
        data = True
        previous_results = False
        count = 0
        while data:
            _logger.info('Calling M2 for Products with Page: %s and Page Size: %s'% (current_page, page_size))
            call_url = url + '&searchCriteria[currentPage]=%s&searchCriteria[pageSize]=%s'% (current_page, page_size)
            current_page += 1
            data = self._get_job_data(job, call_url, False)

            #Fix for core bug
            if data['items'][0]['sku'] == previous_results:
                _logger.info('There are no more results')
                break

            previous_results = data['items'][0]['sku']
            records = []
            for product in data['items']:
                for attribute in product['custom_attributes']:
                    product[attribute['attribute_code']] = attribute['value']
                    product['entity_id'] = product['id']
                records.append(product)

            self.process_mage_products_response(job, records)


    def process_mage_products_response(self, job, records):
        product_obj = self.env['product']

        error_count = 0
        for record in records:
            #Solves bug with null sku
            if not record['sku']:
                continue
            if record.get('type_id') != 'simple':
                continue
#            if str(record.get('status')) == '2':
 #               continue
            try:
                vals = product_obj.prepare_odoo_record_vals(job, record)
                product_id = product_obj.upsert_mage_record(vals)
                product = product_obj.browse(product_id)
#                _logger.info('Successfully synced product with SKU: %s' % record['sku'])
                self.env.cr.commit()

            except Exception as e:
                _logger.error('Exception with product sync from Magento')
                _logger.error(str(e))
                subject = 'Too many errors ocurred with Mage product sync to continue'
                self.env['integrator.logger'].submit_event('Magento 2x', subject, str(e), False, 'admin')
                return False

        return True
