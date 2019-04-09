# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.osv import osv
from datetime import datetime
import time
from odoo.tools.translate import _
from odoo.exceptions import ValidationError,Warning



class training(models.Model):
    _name = 'training.training'
    _inherit = ['mail.thread' ]
    _rec_name = 'course_name'



    def _default_employee(self):
        return self.env.context.get('default_employee_id') or self.env['hr.employee'].search(
            [('user_id', '=', self.env.uid)], limit=1)

    course_name = fields.Many2one(comodel_name='course.schedule', string='Course', track_visibility='onchange',required='1')
    price_id = fields.Float(string='Price', readonly='True', related='course_name.price',store=True)
    bio_content = fields.Text(string='Contents', readonly='True', related='course_name.bio_cont')
    employee_id = fields.Many2one(comodel_name='hr.employee', string='Employee', index=True, track_visibility='onchange', readonly=True,
                                  states={'draft': [('readonly', False)], 'hod': [('readonly', False)]},
                                  default=_default_employee)

   
    bio_agrement = fields.Text(string='Agreements', related='course_name.bio', readonly='True')
    state = fields.Selection(selection=[('draft', 'Draft'), ('progress', 'Progress'), ('pending', 'Pending'),
                                        ('approve', 'Approved'), ('done', 'Done'), ('cancel', 'Canceled')
                                        ], default='draft', track_visibility='onchange')
    cours_typ = fields.Selection(selection=[('t', 'Technical'), ('s', 'Soft Skills')], default='t',
                                  readonly=True,related='course_name.course_typ')

    user_id = fields.Many2one('res.users', string='User', related='employee_id.user_id', related_sudo=True,
                                         default=lambda self: self.env.uid, readonly=True)
    department_id = fields.Many2one('hr.department', 'Department', 
                                track_visibility='onchange', related='employee_id.department_id',store=True)
    company_id = fields.Many2one('res.company', 'Company', track_visibility='onchange')
    is_agreement = fields.Boolean('Agree',help="If you checked mean you are agree to take this course")
    date_from = fields.Date(string='From', related='course_name.f_date',readonly=True, store=True)
    date_to = fields.Date(string='To', related='course_name.to_date',readonly=True, store=True)
    create_date = fields.Datetime('Creation Date',default=lambda *a: time.strftime('%Y-%m-%d %H:%M:%S',),readonly=True)
    evaluate = fields.Selection(selection=[('n', 'Not Satisfied'),('y', 'Satisfied')], default='y',string='Program Evaluation',
                                domain={'invisible': [('state','!=','done')]}, track_visibility='onchange')


    @api.constrains('date_from', 'date_to')
    def _check_date(self):
        for course in self:
            domain = [
                ('date_from', '<=', course.date_to),
                ('date_to', '>=', course.date_from),
                ('employee_id', '=', course.employee_id.id),
                ('id', '!=', course.id),
                ('state', 'not in', ['cancel']),
            ]
            ncourse = self.search_count(domain)
            if ncourse:
                raise ValidationError(_('You can not have 2 courses that overlaps on same day!'))

    #Check Tags
    @api.onchange("employee_id")
    @api.multi
    def _get_cat(self):
        schedule=self.env['course.schedule']
        list1 = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1).category_ids.ids
        schedule_ids=[]
        for sc in schedule.search([]):
            list2=sc.tags.ids
            match = any(map(lambda v: v in list1, list2))
            if match :
                schedule_ids.append(sc.id)
        return {'domain': {'course_name': [('id', 'in', schedule_ids),('state', '=', 'active')]}}


    #User can delete record only in draft,cancel status
    def unlink(self):
        for rec in self:
            if rec.state not in ['draft', 'cancel']:
                raise osv.except_osv(_('Warning!'),_('You cannot delete a Course which is in %s state.')%(rec.state))
        return super(training, self).unlink()

    @api.multi
    def action_new(self):
        self.state = 'draft'

    @api.multi
    def action_hod(self):
        if self.is_agreement == True:
            self.state = 'progress'
        else:
            raise osv.except_osv(_('Warning!'), _("Please make sure you have read the agreement and click on 'Agree'"))

    @api.multi
    def action_hrman(self):
        self.state = 'pending'

    @api.multi
    def action_approve(self):
        self.state = 'approve'

    @api.multi
    def action_close(self):
        self.state = 'done'

    @api.multi
    def action_cancel(self):
        self.state = 'cancel'


class CourseSchedule(models.Model):
    _name = 'course.schedule'
    _inherit = ['mail.thread']
    _rec_name = 'text'



    #Calculate Remaining Persons
    @api.one
    @api.depends('capacity', 'reserv')
    def calc_remain(self):
        if self.capacity or self.reserv:
            if self.capacity >= self.reserv:
                self.remain = self.capacity - self.reserv



    #Calcaulate Reservsion Persons
    @api.multi
    def compute_reserv(self):
        calc_reserv = self.env['training.training']
        for sch in self:
            sch.reserv = calc_reserv.search_count([('course_name.id', '=', sch.id), ('state', '!=', 'cancel')])
            if sch.reserv == sch.capacity:
                sch.write({'state': 'close'})
            elif sch.reserv < sch.capacity:
                sch.write({'state': 'active'})
        return sch.id




    #Calaualte Total Days of Course
    @api.onchange('f_date','to_date')
    def _calc_days(self):
        if self.f_date and self.to_date and self.f_date <= self.to_date:
            date_format = "%Y-%m-%d"
            start_date = datetime.strptime(str(self.f_date),date_format)
            end_date = datetime.strptime(str(self.to_date),date_format)
            res = end_date - start_date
            self.duration = str(int(res.days+1))

    course_id = fields.Many2one(comodel_name='course.training', track_visibility='onchange', string='Course',required='1')
    duration = fields.Integer('Duration', track_visibility='onchange')
    f_date = fields.Date(string='From',required=True, track_visibility='onchange')
    to_date = fields.Date(string='To',required=True, track_visibility='onchange')
    capacity = fields.Integer(string='Capacity', track_visibility='onchange')
    tags = fields.Many2many('hr.employee.category', 'sch_category_rel', 'sch_id', 'category_id', string='Tags')
    price = fields.Float(string='Price', related='course_id.price_ids', readonly=True)
    trainer_id = fields.Many2one(comodel_name='partner.trainer', string='Trainer', track_visibility='onchange')
    image = fields.Binary('Image',related='trainer_id.image_id')
    hours = fields.Float('Hours', track_visibility='onchange')
    reserv = fields.Integer(string='Reservation', compute='compute_reserv')
    remain = fields.Integer(string='Remaining', compute='calc_remain')
    bio = fields.Text(string='Bio', track_visibility='onchange')
    state = fields.Selection(selection=[('new', 'New'), ('active', 'Active'), ('close', 'Closed')
                                        ], default='new', track_invisiblty='onchange')
    text = fields.Char(string='Cou', related='course_id.course')
    course_typ = fields.Selection(selection=[('t','Technical'),('s','Soft Skills')],readonly=True,default='t',related='course_id.course_type')
    address = fields.Char('Address')
    bio_cont = fields.Text('Bio', related='course_id.bio_course')
    training = fields.One2many(comodel_name='training.training', inverse_name='course_name', string='Train', track_visibility='onchange')



    @api.multi
    def action_new(self):
        self.state = 'new'

    @api.multi
    def action_active(self):
        self.state = 'active'

    @api.multi
    def action_close(self):
        self.state = 'close'


# ===============>>>>>>>>================<<<<<<<<<<<==============

class PartnerTrainer(models.Model):
    _name = 'partner.trainer'
    _inherit = ['mail.thread']
    _rec_name = 'partner_name'

    partner_name = fields.Many2one(comodel_name='res.partner', track_visibility='onchange', string='Trainer',required=True, domain=[('is_trainer', '=', True)])
    image_id = fields.Binary('Image', related='partner_name.image')




    _

# =======================>>>>>==================<<<<<==================

class CourseTraining(models.Model):
    _name = 'course.training'
    _inherit = ['mail.thread']
    _rec_name = 'course'

    course = fields.Char(string='Course Name',required='1', track_visibility='onchange')
    code = fields.Char(string='Code', track_visibility='onchange')
    course_type = fields.Selection(selection=[('t','Technical'),('s','Soft Skills')],default='t', track_visibility='onchange')
    bio_course = fields.Text('Bio', track_visibility='onchange')
    price_ids = fields.Float(string='Price',required='1', track_visibility='onchange')

    _sql_constraints = [
        ('course_code_unique',
         'UNIQUE(code)',
         'Code Must be Unique'),
    ]




class ResPartner(models.Model):
    _inherit = 'res.partner'
    is_trainer = fields.Boolean('Is a Trainer',default=True)


# ======================================================================

class HREmployee(models.Model):
    # _name = 'hr.employee'
    _inherit = 'hr.employee'

    @api.multi
    def _calc_course(self):
        for course in self:
            course_ids = self.env['training.training'].search([('employee_id', '=', course.id)])
            course.cour_ids = len(course_ids)

    cour_ids = fields.Integer('Course', compute='_calc_course')
    hr_traiing_ids = fields.One2many(comodel_name='training.training',inverse_name='employee_id',string='Training')
    # total_courses_price = fields.Float('Total Amount',compute='compute_total_amount')
    total_rewards = fields.Float('Rewads Amount')





    # @api.one
    # def compute_total_amount(self):
    #     total = 0.00
    #     for line in self.hr_traiing_ids:
    #         if line.state != 'cancel':
    #             total += line.price_id
    #             print('TTTTTTTTTTTTTTTTTTTTTT',total)
    #     self.total_courses_price = total
    #
    #     print('XXXXXXXXXXXXXXXXXXX',self.total_courses_price)









