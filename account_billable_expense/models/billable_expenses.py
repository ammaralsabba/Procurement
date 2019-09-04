# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.tools.misc import formatLang


class BillableExpenses(models.Model):
    _name = 'billable.expenses'
    _description = 'Billable Expenses'
    _rec_name = 'description'

    bill_id = fields.Many2one('account.invoice')
    bill_line_id = fields.Many2one('account.invoice.line')  # expense created from a bill line
    description = fields.Text('Description')
    amount = fields.Monetary('Amount')
    bill_date = fields.Date('Date')

    currency_id = fields.Many2one('res.currency',
                                  readonly=True, default=lambda self: self.env.user.company_id.currency_id)
    customer_id = fields.Many2one('res.partner', 'Customer')

    invoice_line_id = fields.Many2one('account.invoice.line')  # expense added to an invoice line
    is_outstanding = fields.Boolean('Outstanding', compute='_get_outstanding_state', store=True)

    # for report
    source_document = fields.Char('Source Document', compute='_compute_source_document', store=True)
    supplier_id = fields.Many2one('res.partner', 'Supplier', compute='_compute_supplier_id', store=True)

    @api.depends('invoice_line_id', 'invoice_line_id.invoice_id.state')
    def _get_outstanding_state(self):
        for record in self:
            if not record.invoice_line_id or (record.invoice_line_id and
                                              record.invoice_line_id.invoice_id.state == 'draft'):
                record.is_outstanding = True
            else:
                record.is_outstanding = False

    @api.depends('bill_id')
    def _compute_source_document(self):
        for record in self:
            record.source_document = record.bill_id.number if record.bill_id else ''

    @api.depends('bill_id')
    def _compute_supplier_id(self):
        for record in self:
            record.supplier_id = record.bill_id.partner_id if record.bill_id else False

    def _get_log_msg(self, vals):
        current_customer = self.customer_id
        new_customer = self.env['res.partner'].browse(vals['customer_id'])
        formatted_amount = formatLang(self.env, self.amount, currency_obj=self.env.user.company_id.currency_id)

        if not new_customer:  # remove case
            msg = 'Billable expense %s %s removed' % (self.description, formatted_amount)
        else:
            customer_link = '<a href=javascript:void(0) data-oe-model=res.partner data-oe-id=%d>%s</a>' % \
                            (new_customer.id, new_customer.name)
            if not current_customer:  # assign
                msg = 'Billable expense %s %s assigned to %s' % \
                      (self.description, formatted_amount, customer_link)
            else:  # re-assign
                msg = 'Billable expense %s %s re-assigned to %s' % \
                      (self.description, formatted_amount, customer_link)

        return msg

    def _log_message_expense(self, vals):
        """
        Split into different function so we can inherit purchase_billable_expense
        """
        for record in self:
            msg = record._get_log_msg(vals)
            record.bill_id.message_post(body=msg, subtype='account_billable_expense.mt_billable_expense')

    @api.multi
    def write(self, vals):
        if 'customer_id' in vals:
            vals['invoice_line_id'] = False  # reassign expense for another customer
            self._log_message_expense(vals)

        res = super(BillableExpenses, self).write(vals)

        return res
