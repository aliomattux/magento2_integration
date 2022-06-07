from odoo import api, fields, models, SUPERUSER_ID, _, exceptions
from datetime import datetime, timedelta

class MageSetup(models.Model):
    _name = 'mage.setup'

    name = fields.Char('Name', required=True)
    debug_mode = fields.Selection([('none', 'None'), ('error', 'Error'), ('debug', 'All')], 'Debug Mode')
    url = fields.Char('URL', required=True)
    username = fields.Char('Username')
    password = fields.Char('Password')
    token = fields.Char('Token')
    token_expiration = fields.Datetime('Token Expiration')


    def button_refresh_access_token(self):
        record = self
        return self.refresh_access_token(record)


    def prepare_url(self, setup, operation):
        url = setup.url
        url += 'index.php/rest/V1' + operation
        return url


    def refresh_access_token(self, setup):
        import requests
        import json

        data = {
            'username': setup.username,
            'password': setup.password,
        }

        headers = {
            'Content-Type': 'application/json',
        }

        url = self.prepare_url(setup, '/integration/admin/token')
        r = requests.post(url,
            headers=headers,
            data=json.dumps(data)
        )

        if r.status_code != 200:
            raise exceptions.UserError(str(r.status_code)+' '+r.text)

        access_token = r.text.replace('"', '')
        setup.token = access_token
        setup.token_expiration = datetime.utcnow() + timedelta(hours=3)
        self.env.cr.commit()
        return access_token


class MageWebsite(models.Model):
    _name = 'mage.website'

    name = fields.Char('Name')
    code = fields.Char('Code')
    is_default = fields.Boolean('Default Website')
    default_store_group = fields.Many2one('mage.store.group', 'Default Store Group')
    sort_order = fields.Integer('Sort Order')
    entity_id = fields.Integer('External Id')


    def prepare_odoo_record_vals(self, job, record):
        return {
            'is_default': record['is_default'],
            'entity_id': record['website_id'],
            'code': record['code'],
            'sort_order': record['sort_order'],
            'name': record['name'],
        }


class MageStoreGroup(models.Model):
    _name = 'mage.store.group'

    name = fields.Char('Name')
    website = fields.Many2one('mage.website', 'Website')
    entity_id = fields.Integer('External Id')
    default_store_view = fields.Many2one('mage.store.view', 'Default Store View')
    store_views = fields.One2many('mage.store.view', 'store', 'Store Views')


    def prepare_odoo_record_vals(self, job, record):
        website_obj = self.env['mage.website']
        return {
                'website': website_obj.get_mage_record(record['website_id']),
                'entity_id': record['group_id'],
                'name': record['name'],
        }


class MageStoreView(models.Model):
    _name = 'mage.store.view'

    name = fields.Char('Name')
    manual_order_number = fields.Char('Manual Order Number')
    store = fields.Many2one('mage.store.group', 'Store Group')
    code = fields.Char('Code')
    website = fields.Many2one('mage.website', 'Website')
    entity_id = fields.Integer('Entity Id')
    sort_order = fields.Integer('Sort Order')
    import_orders_start_datetime = fields.Datetime('Import Orders from This Time')
    import_orders_end_datetime = fields.Datetime('Import Orders To This Time')
    last_import_datetime = fields.Datetime('Last Imported At')
    last_export_datetime = fields.Datetime('Last Exported At')


    def prepare_odoo_record_vals(self, job, record):
        website_obj = self.env['mage.website']
        group_obj = self.env['mage.store.group']
        return {
                'website': website_obj.get_mage_record(record['website_id']),
                'code': record['code'],
                'name': record['name'],
                'sort_order': record['sort_order'],
                'entity_id': record['store_id'],
                'store': group_obj.get_mage_record(record['group_id']),

        }
