from odoo import api, fields, models, SUPERUSER_ID, _

class MageJob(models.Model):
    _name = 'mage.job'
    name = fields.Char('Name', required=True)
    core_job = fields.Boolean('Core Job')
    mage_instance = fields.Many2one('mage.setup', 'Magento Instance', required=True)
    scheduler = fields.Many2one('ir.cron', 'Scheduler', readonly=True)
    mapping = fields.Many2one('mage.mapping', 'Mapping')
    python_model = fields.Many2one('ir.model', 'Python Model')
    python_function_name = fields.Char('Python Function Name')


    def button_execute_job(self):
        job = self
        result = self.import_resources(job)

        return True


    def import_resources(self, job):
        """
        """
        job_obj = self.env[job.python_model.name]
        return getattr(job_obj, job.python_function_name)(job)

        return False


    def button_schedule_mage_job(self):
        for job in self:
            if job.scheduler:
                continue
            cron_id = self.create_mage_schedule(job.id, job.name)
            self.write(job.id, {'scheduler': cron_id})
        return True


    def create_mage_schedule(self, job_id, job_name):
        vals = {'name': job_name,
                'active': False,
                'user_id': SUPERUSER_ID,
                'interval_number': 15,
                'interval_type': 'minutes',
                'numbercall': -1,
                'doall': False,
                'model': 'mage.job',
                'function': 'button_execute_job',
                'args': '([' + str(job_id) +'],)',
        }

        return self.env['ir.cron'].create(vals)
