import base64
import os
from io import BytesIO

import pdfkit
import qrcode
from django.core.files.base import ContentFile
from django.template.loader import get_template
from django.utils import timezone

from apps.company.models import EnvModel
from apps.document.helpers import upload_file
from apps.document.models import File
from utils.constants import CONSTANTS


class BasePDFConfig:
    def generate_qrcode_base64(self, check_id):
        VERIFY_URL = os.getenv('DOC_VERIFICATION_URL')
        input_string = f"{VERIFY_URL}home?check={check_id}"
        # Create a QR code instance
        qr = qrcode.QRCode(version=1,
                           error_correction=qrcode.constants.ERROR_CORRECT_M,
                           box_size=10,
                           border=4)

        # Add the input string to the QR code
        qr.add_data(input_string)
        qr.make(fit=True)

        # Create an image from the QR code
        qr_image = qr.make_image(fill_color="black", back_color="white")

        # Create an in-memory stream
        stream = BytesIO()

        # Save the image to the stream in PNG format
        qr_image.save(stream, "PNG")

        # Rewind the stream to the beginning
        stream.seek(0)

        # Read the stream content as bytes
        image_bytes = stream.read()

        # Encode the image bytes as base64
        encoded_string = base64.b64encode(image_bytes).decode('utf-8')

        return encoded_string

    def get_logo_and_name(self, env_id):
        env = EnvModel.objects.get(code=env_id)
        return env.name_uz, env.name_ru, env.company_logo, env.logo_size

    def get_signers(self, signer_data, check_id=None):
        signer_info = ''

        b64 = self.generate_qrcode_base64(check_id)

        for signer in signer_data:
            is_signed = signer.get('is_signed')
            if is_signed is True:
                signer_info += f"""                
                    <table style="width: 100%; padding: 0 24px; margin-bottom: 8px; margin-top: 24px">
                        <tr>
                            <td style="font-size: 14px; font-weight: bolder; width: 50%;">
                                {signer.get('position')}
                            </td>
                            <td style="width: 25%;">
                                <div style="width: 70px; height: 70px;">
                                    <img style="width: 70px; height: 70px; border: none;" src="data:image/png;base64, {b64}" alt="qr-code"/>
                                </div>
                            </td>
                            <td style="font-size: 14px; font-weight: bolder; width: 25%;">
                                {signer.get('name')}
                            </td>
                        </tr>
                    </table>
                """
            else:
                signer_info += f"""
                    <table class="w-full" style="padding: 0 24px; margin-bottom: 8px;">
                            <tr>
                                <td class="text-14 font-semibold" style="width: 50%;">
                                    {signer.get('position')}
                                </td>
                                <td style="width: 25%;">
                                    <span></span>
                                </td>
                                <td class="text-14 font-semibold" style="width: 25%;">
                                    {signer.get('name')}
                                </td>
                            </tr>
                    </table>
                """

        return signer_info

    def get_receivers(self, receivers, type=None):
        receivers_info = ''
        if type == 'new_receivers':
            for receiver in receivers:
                receivers_info += f"""<tr>
                    <td style="width: 60%"></td>
                    <td style="text-align: end; font-weight: 600; padding-bottom: 4px; width: 40%" class="small-1">
                    {receiver['correspondent_name']}
                    </td>
                </tr>"""
        else:
            for receiver in receivers:
                receivers_info += f"""<tr>
            <td style="width: 30%;"></td>
            <td style="width: 70%; vertical-align: top; text-align: end">
                <div class="text-14 font-semibold" style="margin-bottom: 4px">{receiver.get('name')}</div>
            </td></tr>"""
        return receivers_info

    def render_pdf(self, template_name: str, context: dict) -> bytes:
        """
        Render pdf from html template
        """
        template = get_template(template_name)
        html_content = template.render(context)
        options = {
            'dpi': 365,
            'page-size': 'A4',
            'encoding': "UTF-8",
            'zoom': '1.3',
            'custom-header': [('Accept-Encoding', 'gzip')],
            'no-outline': None,
        }
        return pdfkit.from_string(html_content, False, options=options)

    def save_pdf(self, pdf_data: bytes, filename: str, module: str) -> int:
        """
        Save pdf data to the database
        """
        size_bytes = len(pdf_data)
        year = timezone.now().year

        # Upload
        response = upload_file(ContentFile(pdf_data), module, filename)
        object_key = response.get("key")
        key_etag = response.get("key_etag")
        sha256_hex = response.get("sha256")
        etag = response.get("etag")
        version_id = response.get("version_id")
        bucket_name = response.get("bucket")

        file_instance = File.objects.create(
            key=key_etag,
            name=filename,
            extension='pdf',
            size=size_bytes,
            module=module,
            year=year,
            content_type='application/pdf',
            path=object_key,
            bucket=bucket_name,
            sha256=sha256_hex,
            etag=etag,
            state="uploaded",
            version_id=version_id
        )
        return file_instance.id


class GenerateInnerLetterToPdf(BasePDFConfig):
    TEMPLATE_NAME = 'letters/service.html'

    def __init__(self, check_id, content, signers, receivers, executor, phone, created_date, signed_date,
                 register_number, register_date, sender, env_id):
        name_uz, name_ru, company_logo, logo_size = self.get_logo_and_name(env_id)
        self.context = {
            'content': content,
            'check_id': check_id,
            'signers': signers,
            'receivers': receivers,
            'executor': executor,
            'phone': phone,
            'created_date': created_date,
            'signed_date': signed_date,
            'register_number': register_number,
            'register_date': register_date,
            'sender': sender,
            'company_name_uz': name_uz,
            'company_name_ru': name_ru,
            'company_logo': company_logo,
            'logo_size': logo_size
        }

    def generate_pdf(self) -> int:
        self.context['signers'] = self.get_signers(self.context['signers'], self.context['check_id'])
        self.context['receivers'] = self.get_receivers(self.context['receivers'])
        pdf_data = self.render_pdf(self.TEMPLATE_NAME, self.context)
        return self.save_pdf(pdf_data, f"{self.context['check_id']}.pdf", 'service_letters')


class GenerateApplicationToPDF(BasePDFConfig):
    TEMPLATE_NAME = 'letters/application.html'

    def __init__(self, check_id, content, signers, executor, phone, created_date, signed_date, basic_signer,
                 basic_signer_position, user_name, user_position, user_department, env_id, document_sub_type_id):
        name_uz, name_ru, company_logo, logo_size = self.get_logo_and_name(env_id)
        self.context = {
            'content': content,
            'check_id': check_id,
            'signers': signers,
            'executor': executor,
            'phone': phone,
            'created_date': created_date,
            'signed_date': signed_date,
            'basic_signer': basic_signer,
            'basic_signer_position': basic_signer_position,
            'user_name': user_name,
            'user_position': user_position,
            'user_department': user_department,
            'company_name_uz': name_uz,
            'company_name_ru': name_ru,
            'company_logo': company_logo,
            'logo_size': logo_size,
            'document_sub_type_id': document_sub_type_id
        }

    def generate_pdf(self) -> int:
        self.context['signers'] = self.get_signers(self.context['signers'], self.context['check_id'])
        self.context['qr_code'] = self.generate_qrcode_base64(self.context['check_id'])
        pdf_data = self.render_pdf(self.TEMPLATE_NAME, self.context)
        return self.save_pdf(pdf_data, f"{self.context['check_id']}.pdf", 'applications')


class GenerateTripNoticeToPdf(BasePDFConfig):
    """
    Generate trip notice to pdf
    """
    TEMPLATE_NAME = 'letters/trip_notice.html'

    def __init__(self, check_id, content, signers, trip_info,
                 executor, phone, created_date, signed_date,
                 register_number, register_date, sender,
                 performers, curator_name, curator_position, short_description, env_id):
        qr_b64 = self.generate_qrcode_base64(check_id)
        name_uz, name_ru, company_logo, logo_size = self.get_logo_and_name(env_id)
        self.context = {
            'content': content,
            'short_description': short_description,
            'check_id': check_id,
            'signers': signers,
            'executor': executor,
            'phone': phone,
            'created_date': created_date,
            'signed_date': signed_date,
            'register_number': register_number,
            'register_date': register_date,
            'sender': sender,
            'trip_information': trip_info,
            'performers': performers,
            'curator_name': curator_name,
            'curator_position': curator_position,
            'qr_b64': qr_b64,
            'company_name_uz': name_uz,
            'company_name_ru': name_ru,
            'company_logo': company_logo,
            'logo_size': logo_size
        }

    def generate_pdf(self) -> int:
        self.context['signers'] = self.get_signers(self.context['signers'], self.context['check_id'])
        # self.context['receivers'] = self.get_receivers(self.context['receivers'])
        pdf_data = self.render_pdf(self.TEMPLATE_NAME, self.context)
        return self.save_pdf(pdf_data, f"{self.context['check_id']}.pdf", 'trip_notices')


class GenerateNoticeToPdf(BasePDFConfig):
    """
    Generate trip notice to pdf
    """
    TEMPLATE_NAME = 'letters/notice.html'

    def __init__(self, check_id, content, signers, executor, phone, created_date, signed_date, short_description,
                 register_number, register_date, sender, performers, curator_name, curator_position, env_id):
        qr_b64 = self.generate_qrcode_base64(check_id)
        name_uz, name_ru, company_logo, logo_size = self.get_logo_and_name(env_id)
        self.context = {
            'content': content,
            'short_description': short_description,
            'check_id': check_id,
            'signers': signers,
            'executor': executor,
            'phone': phone,
            'created_date': created_date,
            'signed_date': signed_date,
            'register_number': register_number,
            'register_date': register_date,
            'sender': sender,
            'performers': performers,
            'curator_name': curator_name,
            'curator_position': curator_position,
            'qr_b64': qr_b64,
            'company_name_uz': name_uz,
            'company_name_ru': name_ru,
            'company_logo': company_logo,
            'logo_size': logo_size
        }

    def generate_pdf(self) -> int:
        self.context['signers'] = self.get_signers(self.context['signers'], self.context['check_id'])
        # self.context['receivers'] = self.get_receivers(self.context['receivers'])
        pdf_data = self.render_pdf(self.TEMPLATE_NAME, self.context)
        return self.save_pdf(pdf_data, f"{self.context['check_id']}.pdf", 'notices')


class GenerateOrderToPdf(BasePDFConfig):
    """
    Generate trip notice to pdf
    """
    TEMPLATE_NAME = 'letters/hr_order.html'

    def __init__(self, check_id, content, signers, executor, phone,
                 register_number, register_date, negotiators, env_id):
        qr_b64 = self.generate_qrcode_base64(check_id)
        name_uz, name_ru, company_logo, logo_size = self.get_logo_and_name(env_id)
        self.context = {
            'content': content,
            'check_id': check_id,
            'signers': signers,
            'executor': executor,
            'phone': phone,
            'register_number': register_number,
            'register_date': register_date,
            'negotiators': negotiators,
            'qr_b64': qr_b64,
            'company_name_uz': name_uz,
            'company_name_ru': name_ru,
            'company_logo': company_logo,
            'logo_size': logo_size
        }

    def generate_pdf(self) -> int:
        self.context['signers'] = self.get_signers(self.context['signers'], self.context['check_id'])
        self.context['negotiators'] = self.get_signers(self.context['negotiators'], self.context['check_id'])
        pdf_data = self.render_pdf(self.TEMPLATE_NAME, self.context)
        return self.save_pdf(pdf_data, f"{self.context['check_id']}.pdf", 'hr_orders')


class GenerateDecreeToPdf(BasePDFConfig):
    """
    Generate trip decree to pdf
    """

    def __init__(self, check_id, content, signers, executor, phone,
                 register_number, register_date, trips=None,
                 doc_sub_type=None, env_id=None,
                 trip_notice_number=None, trip_v2=None):

        self.doc_sub_type = doc_sub_type

        if doc_sub_type in [10]:
            self.TEMPLATE_NAME = 'letters/trip_decree.html'
        elif doc_sub_type in [36, 28, 38, 41]:
            self.TEMPLATE_NAME = 'letters/trip_decree_v2.html'
        else:
            self.TEMPLATE_NAME = 'letters/decree.html'

        qr_b64 = self.generate_qrcode_base64(check_id)
        name_uz, name_ru, company_logo, logo_size = self.get_logo_and_name(env_id)
        self.context = {
            'content': content,
            'check_id': check_id,
            'signers': signers,
            'executor': executor,
            'phone': phone,
            'register_number': register_number,
            'register_date': register_date,
            'qr_b64': qr_b64,
            'trips': trips,
            'company_name_uz': name_uz,
            'company_name_ru': name_ru,
            'company_logo': company_logo,
            'logo_size': logo_size,
            'trip_notice_number': trip_notice_number,
            'groups': trip_v2,
            'doc_sub_type': doc_sub_type
        }

    def generate_pdf(self) -> int:
        self.context['signers'] = self.get_signers(self.context['signers'], self.context['check_id'])
        pdf_data = self.render_pdf(self.TEMPLATE_NAME, self.context)

        if self.doc_sub_type in [10, 28]:
            module_name = 'trip_decrees'
        elif self.doc_sub_type in [36]:
            module_name = 'trip_decrees_v2'
        else:
            module_name = 'decrees'
        return self.save_pdf(pdf_data, f"{self.context['check_id']}.pdf", module_name)


class GenerateLocalTripOrderToPdf(BasePDFConfig):
    """
    Generate trip decree to pdf
    """
    TEMPLATE_NAME = 'letters/local_trip_order.html'

    def __init__(self, check_id, content, signers, executor, phone,
                 register_number, register_date, curator, trips=None, env_id=None):
        qr_b64 = self.generate_qrcode_base64(check_id)
        name_uz, name_ru, company_logo, logo_size = self.get_logo_and_name(env_id)
        self.context = {
            'content': content,
            'check_id': check_id,
            'signers': signers,
            'executor': executor,
            'phone': phone,
            'register_number': register_number,
            'register_date': register_date,
            'qr_b64': qr_b64,
            'trips': trips,
            'curator': curator,
            'company_name_uz': name_uz,
            'company_name_ru': name_ru,
            'company_logo': company_logo,
            'logo_size': logo_size
        }

    def generate_pdf(self) -> int:
        self.context['signers'] = self.get_signers(self.context['signers'], self.context['check_id'])
        self.context['curator'] = self.get_signers(self.context['curator'], self.context['check_id'])
        pdf_data = self.render_pdf(self.TEMPLATE_NAME, self.context)
        return self.save_pdf(pdf_data, f"{self.context['check_id']}.pdf", 'local_trip_orders')


class GeneratePowerOfAttorneyToPdf(BasePDFConfig):
    """
    Generate power of attorney to pdf
    """
    TEMPLATE_NAME = 'poa/power_of_attorney.html'

    def __init__(self, check_id, curator_name, curator_position,
                 signers, executor, phone, employee_position, employee_name,
                 start_date, end_date, passport_series, passport_number,
                 passport_issued_by, passport_issued_date,
                 created_date, signed_date, register_number,
                 trips=None, env_id=None, **kwargs):
        qr_b64 = self.generate_qrcode_base64(check_id)
        name_uz, name_ru, company_logo, logo_size = self.get_logo_and_name(env_id)
        doc_sub_type = kwargs.get('document_sub_type')

        if doc_sub_type == CONSTANTS.DOC_TYPE_ID.POA_ACTING_FILIAL_MANAGER:
            self.TEMPLATE_NAME = 'poa/poa_acting_filial_manager.html'
        elif doc_sub_type in [CONSTANTS.DOC_TYPE_ID.POA_DEPUTY_FILIAL_MANAGER,
                              CONSTANTS.DOC_TYPE_ID.POA_BSO_DEPUTY_MANAGER_BUSINESS]:
            self.TEMPLATE_NAME = 'poa/poa_deputy_filial_manager.html'
        elif doc_sub_type == CONSTANTS.DOC_TYPE_ID.POA_SECOND_TYPE_BSC_MANAGER:
            self.TEMPLATE_NAME = 'poa/poa_second_type_bsc_manager.html'
        elif doc_sub_type in [CONSTANTS.DOC_TYPE_ID.POA_DEPUTY_FILIAL_MANAGER_RETAIL,
                              CONSTANTS.DOC_TYPE_ID.POA_BSO_DEPUTY_MANAGER_RETAIL]:
            self.TEMPLATE_NAME = 'poa/poa_deputy_filial_manager_retail.html'
        elif doc_sub_type == CONSTANTS.DOC_TYPE_ID.POA_BSO_MANAGER:
            self.TEMPLATE_NAME = 'poa/poa_bso_manager.html'
        elif doc_sub_type in [CONSTANTS.DOC_TYPE_ID.POA_BSO_CLIENT_MANAGER,
                              CONSTANTS.DOC_TYPE_ID.POA_BSC_CLIENT_MANAGER]:
            self.TEMPLATE_NAME = 'poa/poa_client_manager.html'
        elif doc_sub_type in [CONSTANTS.DOC_TYPE_ID.POA_ELECTRON_DIGITAL_SIGNATURE,
                              CONSTANTS.DOC_TYPE_ID.POA_BSC_ELECTRON_DIGITAL_SIGNATURE]:
            self.TEMPLATE_NAME = 'poa/poa_electron_digital_signature.html'
        elif doc_sub_type == CONSTANTS.DOC_TYPE_ID.POA_OPERATIVE_GROUP_HEAD:
            self.TEMPLATE_NAME = 'poa/poa_operative_group_head.html'
        elif doc_sub_type == CONSTANTS.DOC_TYPE_ID.POA_EMPLOYER_REPRESENTATIVE:
            self.TEMPLATE_NAME = 'poa/poa_employer_representative.html'
        elif doc_sub_type in [CONSTANTS.DOC_TYPE_ID.POA_RETURN_ENFORCEMENT_DOCUMENT,
                              CONSTANTS.DOC_TYPE_ID.POA_MEDIATION_AGREEMENT]:
            self.TEMPLATE_NAME = 'poa/poa_return_enforcement_document.html'
        elif doc_sub_type == CONSTANTS.DOC_TYPE_ID.POA_EMPLOYER_REPRESENTATIVE_CHAIRMAN_DEPUTIES:
            self.TEMPLATE_NAME = 'poa/poa_employer_representative_chairman_deputies.html'
        elif doc_sub_type == CONSTANTS.DOC_TYPE_ID.POA_EMPLOYER_REPRESENTATIVE_FIRST:
            self.TEMPLATE_NAME = 'poa/poa_employer_representative_first.html'
        elif doc_sub_type == CONSTANTS.DOC_TYPE_ID.POA_EMPLOYER_REPRESENTATIVE_GENERAL:
            self.TEMPLATE_NAME = 'poa/poa_employer_representative_general.html'
        elif doc_sub_type == CONSTANTS.DOC_TYPE_ID.POA_EMPLOYER_REPRESENTATIVE_SECOND:
            self.TEMPLATE_NAME = 'poa/poa_employer_representative_second.html'
        else:
            self.TEMPLATE_NAME = 'poa/power_of_attorney.html'

        self.context = {
            'check_id': check_id,
            'signers': signers,
            'executor': executor,
            'phone': phone,
            'register_number': register_number,
            'qr_b64': qr_b64,
            'curator_name': curator_name,
            'curator_position': curator_position,
            'employee_position': employee_position,
            'employee_name': employee_name,
            'start_date': start_date,
            'end_date': end_date,
            'employee_passport_seria': passport_series,
            'employee_passport_number': passport_number,
            'employee_passport_issued_by': passport_issued_by,
            'employee_passport_issue_date': passport_issued_date,
            'company_name_uz': name_uz,
            'company_name_ru': name_ru,
            'company_logo': company_logo,
            'logo_size': logo_size,
            'created_date': created_date,
            'signed_date': signed_date,
            'old_attorney_date': kwargs.get('old_attorney_date'),
            'old_attorney_number': kwargs.get('old_attorney_number'),
            'old_attorney_exists': kwargs.get('old_attorney_exists'),
            'employee_company': kwargs.get('employee_company'),
            'deadline_in_words': kwargs.get('deadline_in_words'),
            'content': kwargs.get('content'),
            'short_description': kwargs.get('short_description'),
            'doc_sub_type': doc_sub_type,
        }

    def generate_pdf(self) -> int:
        self.context['signers'] = self.get_signers(self.context['signers'], self.context['check_id'])
        pdf_data = self.render_pdf(self.TEMPLATE_NAME, self.context)
        return self.save_pdf(pdf_data, f"{self.context['check_id']}.pdf", 'power_of_attorneys')


class GenerateActToPdf(BasePDFConfig):
    TEMPLATE_NAME = 'letters/act.html'

    def __init__(self, check_id, curator_name, curator_position,
                 signers, executor, phone, employee,
                 created_date, signed_date, register_number, register_date,
                 employee_name, env_id=None, **kwargs):
        qr_b64 = self.generate_qrcode_base64(check_id)
        name_uz, name_ru, company_logo, logo_size = self.get_logo_and_name(env_id)

        self.context = {
            'check_id': check_id,
            'signers': signers,
            'executor': executor,
            'phone': phone,
            'register_number': register_number,
            'register_date': register_date,
            'qr_b64': qr_b64,
            'curator_name': curator_name,
            'curator_position': curator_position,
            'employee': employee,
            'company_name_uz': name_uz,
            'company_name_ru': name_ru,
            'company_logo': company_logo,
            'logo_size': logo_size,
            'created_date': created_date,
            'signed_date': signed_date,
            'employee_name': employee_name,
            'content': kwargs.get('content'),
        }

    def generate_pdf(self) -> int:
        pdf_data = self.render_pdf(self.TEMPLATE_NAME, self.context)
        return self.save_pdf(pdf_data, f"{self.context['employee_name']}_{self.context['check_id']}.pdf", 'act')


class GenerateTripNoticeV2ToPdf(BasePDFConfig):
    """
    Generate trip notice v2 to pdf
    """
    TEMPLATE_NAME = 'letters/trip_notice_v2.html'

    def __init__(self, check_id, content, signers, trip_info,
                 executor, phone, created_date, signed_date,
                 register_number, register_date, sender,
                 performers, curator_name, curator_position,
                 short_description, env_id, trip_plan, document_sub_type_id):
        qr_b64 = self.generate_qrcode_base64(check_id)
        name_uz, name_ru, company_logo, logo_size = self.get_logo_and_name(env_id)
        self.context = {
            'content': content,
            'short_description': short_description,
            'check_id': check_id,
            'signers': signers,
            'executor': executor,
            'phone': phone,
            'created_date': created_date,
            'signed_date': signed_date,
            'register_number': register_number,
            'register_date': register_date,
            'sender': sender,
            'groups': trip_info,
            'trip_plans': trip_plan,
            # 'booking_data': booking,
            'performers': performers,
            'curator_name': curator_name,
            'curator_position': curator_position,
            'qr_b64': qr_b64,
            'company_name_uz': name_uz,
            'company_name_ru': name_ru,
            'company_logo': company_logo,
            'logo_size': logo_size,
            'document_sub_type_id': document_sub_type_id,
        }

    def generate_pdf(self) -> int:
        self.context['signers'] = self.get_signers(self.context['signers'], self.context['check_id'])
        # self.context['receivers'] = self.get_receivers(self.context['receivers'])
        pdf_data = self.render_pdf(self.TEMPLATE_NAME, self.context)
        return self.save_pdf(pdf_data, f"{self.context['check_id']}.pdf", 'trip_notices_v2')
