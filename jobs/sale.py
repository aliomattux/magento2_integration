from odoo import api, fields, models, SUPERUSER_ID, _, exceptions
from datetime import datetime, timedelta
import logging
import time
import json
_logger = logging.getLogger(__name__)

class MageIntegrator(models.TransientModel):

    _inherit = 'mage.integrator'

    def get_rest_filters(self, filters):
        filter_string = ''

        filter_count = 0
        for filter in filters:
            filters_prefix = 'searchCriteria[filterGroups][' +str(filter_count)+ '][filters]'
            if filter_count > 0:
                filter_string += '&'
            instance = filters_prefix + '[%s]' % 0
            filter_string += instance + "[field]=" + filter['field']
            filter_string += '&' + instance + "[value]=" + filter['value']
            filter_string += '&' + instance + "[conditionType]=" + filter['condition_type']
            filter_count += 1

        return filter_string


    def test_magento_rest_orders(self, job):
        url = '/orders/257863'
        data = self._get_job_data(job, url, False)
        pp(data)


    def import_magento_rest_orders(self, job):
        url = '/orders?'
        filters = [{
            'field': 'status',
            'value': 'processing',
            'condition_type': 'eq',
        }]
        filters = self.get_rest_filters(filters)
        url += filters
        data = self._get_job_data(job, url, False)
        #API Response returns multiple orders
        for order in data['items']:
            increment_id = order.get('increment_id')
            _logger.info('Processing M2 Order: %s'%increment_id)

            order_obj = self.env['sale']
            #Catch if the order is imported. To override, delete reference from UI
            orders = order_obj.search([('increment_id', '=', increment_id)])
            if orders:
                _logger.info('Order %s already exists in Integrator. Skipping'%increment_id)
                self.add_rest_order_comment(job, order, 'pending_fulfillment', 'Order already Imported')
                continue
            try:
                #Transform vals and send to Nestuite
                res = self.process_one_order(job, order)
                if res:
                    self.add_rest_order_comment(job, order, 'pending_fulfillment', 'Order is Imported')
                else:
                    self.add_rest_order_comment(job, order, 'import_error', '3 Attempts Failed')

                time.sleep(2)

            except Exception as e:
                error_message = str(e)
                if 'ascii' in error_message:
                    error_message = 'One of the address fields contains invalid, non standard characters. Please check the Phone Number/Addresses'

                subject = 'Error Processing M2 Order: %s for Netsuite import'%increment_id
                self.env['integrator.logger'].submit_event('Magento 2x', subject, error_message, True, 'order_integration')
                print('Add Rest order comment')
                self.add_rest_order_comment(job, order, 'import_error', str(e))
        return


    def add_rest_order_comment(self, job, order, status, comment):
        token = self._get_mage_access_token(job)
        order_id = order['entity_id']
        params = '/orders/%s/comments' % order_id
        date_string = datetime.strftime(datetime.utcnow(), '%Y-%m-%d %H:%M:%S')
        data = {
            "statusHistory": {
                "comment": comment,
                "created_at": date_string,
                "parent_id": order_id,
                "is_customer_notified": 0,
                "is_visible_on_front": 0,
                "status": status
            }
        }

        try:
            self._mage_rest_call(job.mage_instance, token, params, data)

        except Exception as e:
            subject = 'Exception occurred when setting Magento 2 Status: %s for order: %s'%(status, order.get('increment_id'))
            self.env['integrator.logger'].submit_event('Magento 2x', subject, str(e), False, 'admin')
        return False


    def process_one_order(self, job, order):
        netsuite_obj = self.env['netsuite.integrator']
        setup_obj = self.env['netsuite.setup']
        netsuite_id = netsuite_obj.get_instance_id()
        netsuite = setup_obj.browse(netsuite_id)
        create_order_url = netsuite.create_order_url
        conn = netsuite_obj.connection(netsuite, url_override=create_order_url)

        sale_obj = self.env['sale']
        netsuite_vals = sale_obj.mage_to_netsuite_vals(job, order)
        sale_vals = {
            'date': order.get('trandate'),
            'entity_id': order.get('order_id'),
            'magento_state': order.get('state'),
            'order_email': netsuite_vals.get('order_email'),
            'increment_id': order.get('increment_id'),
            'mage_order_number': order.get('increment_id'),
            'mage_order_total': netsuite_vals.get('order_total'),
            'name': order.get('increment_id'),
        }

        max_tries = 3
        tries = 1
        for each in [3, 10, 15]:
            try:
                response = conn.request({'order_data': netsuite_vals})
                try:
                    data = json.loads(response)
                except Exception as e:
                    raise exceptions.UserError('Could not decode Netsuite response: Create Sale')
                if not data.get('result'):
                    raise exceptions.UserError('Ntesuite Communication Error: Create Sale')
                if not data['result'] == 'success' and not data.get('internalid'):
                    raise exceptions.UserError('No Internal ID Returned')

                #{'error': {'code': 'UNEXPECTED_ERROR', 'message': 'null'}}
                self.env.cr.commit()
                _logger.info('Order Created in Netsuite Successfully')
                sale_id = sale_obj.create(sale_vals)
                return True

            except Exception as e:
                _logger.critical(e)
                if tries >= max_tries:
                    subject = 'Order: %s Could not be created in Netsuite'%order['increment_id']
                    self.env['integrator.logger'].submit_event('Magento 2x', subject, str(e), True, 'order_integration')
                    return False

                else:
                    time.sleep(each)
                    tries += 1
                    continue

        return False


    def set_one_order_status(self, job, order, status, message):
        try:
            result = self._get_job_data(job, 'sales_order.addComment',\
                [order['increment_id'], status, message])
            return True

        except Exception as e:
            subject = 'Exception occurred when setting Magento Status: %s for order: %s'%(status, order.get('increment_id'))
            self.env['integrator.logger'].submit_event('Magento 2x', subject, str(e), False, 'admin')
        return False

