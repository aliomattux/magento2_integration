from odoo import api, fields, models, SUPERUSER_ID, _, exceptions
from datetime import datetime
import socket
import requests
import json
import logging
_logger = logging.getLogger(__name__)

class MageIntegrator(models.TransientModel):
    _name = 'mage.integrator'

    def get_external_credentials(self):
        mage_obj = self.env['mage.setup']
        setups = mage_obj.search([], limit=1)
        if setups:
            instance = setups[0]
            return {
                'url': instance.url,
                'username': instance.username,
                'password': instance.password,
            }

        else:
            raise exceptions.UserError('You must have already configured Magento to run this function!')


    def _get_credentials(self, job):
        return {
                'url': job.mage_instance.url,
                'username': job.mage_instance.username,
                'password': job.mage_instance.password,
        }


    def _get_mage_access_token(self, job, instance=False):
        if not instance:
            instance = job.mage_instance

        expiration = instance.token_expiration

        if not expiration or not instance.token:
            _logger.info('Token exipiration or token is missing Refreshing')
            return self.env['mage.setup'].refresh_access_token(instance)

        now = datetime.utcnow()
        duration = now - expiration
        duration_in_s = duration.total_seconds()
        hours = divmod(duration_in_s, 3600)[0] * -1
        if hours <= 0:
            _logger.info('Token expired. Refreshing Token')
            return self.env['mage.setup'].refresh_access_token(instance)
        else:
            _logger.info('Existing Token good for %s more hours' % str(hours))
            return instance.token


    def get_magento_region_id(self, credentials, country_id, state_name):
        with API(credentials['url'], credentials['username'], credentials['password']) as mage_api:
            region_id = mage_api.call('sales_order.getregionid', [country_id, state_name])
            return region_id


    def _get_job_data(self, job, method_or_params, arguments, token=False):
        instance = job.mage_instance

        token = self._get_mage_access_token(job)
        return self._mage_rest_call(instance, token, method_or_params, arguments)


    def _mage_rest_call(self, instance, token, method_or_params, data):
        url = self.env['mage.setup'].prepare_url(instance, method_or_params)
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer %s' % token
        }

        if data:
            r = requests.post(url,
                headers=headers,
                data=json.dumps(data)
            )

        else:
            r = requests.get(url,
                headers=headers
            )

        if r.status_code != 200:
            raise exceptions.UserError(r.status_code + ' ' + r.text)

        return json.loads(r.text)
