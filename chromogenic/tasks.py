import re

from datetime import datetime

from celery.decorators import task

from threepio import logger

from core.email import send_image_request_email
from core.models.machine_request import process_machine_request

from chromogenic.drivers.eucalyptus import ImageManager as EucaImageManager
from chromogenic.drivers.openstack import ImageManager as OSImageManager
from chromogenic.drivers.migration import EucaOSMigrater
from chromogenic.drivers.virtualbox import ExportManager

from django.conf import settings

@task()
def machine_export_task(machine_export):
    logger.debug("machine_export_task task started at %s." % datetime.now())
    machine_export.status = 'processing'
    machine_export.save()

    local_download_dir = settings.LOCAL_STORAGE
    exp_provider = machine_export.instance.provider_machine.provider
    provider_type = exp_provider.type.name.lower()
    provider_creds = exp_provider.get_credentials()
    admin_creds = exp_provider.get_admin_identity().get_credentials()
    all_creds = {}
    all_creds.update(provider_creds)
    all_creds.update(admin_creds)
    manager = ExportManager(all_creds)
    #ExportManager().eucalyptus/openstack()
    if 'euca' in exp_provider:
        export_fn = manager.eucalyptus
    elif 'openstack' in exp_provider:
        export_fn = manager.openstack
    else:
        raise Exception("Unknown Provider %s, expected eucalyptus/openstack"
                        % (exp_provider, ))

    meta_name = manager.euca_img_manager._format_meta_name(
        machine_export.export_name,
        machine_export.export_owner.username,
        timestamp_str = machine_export.start_date.strftime('%m%d%Y_%H%M%S'))

    md5_sum, url = export_fn(machine_export.instance.provider_alias,
                             machine_export.export_name,
                             machine_export.export_owner.username,
                             download_dir=local_download_dir,
                             meta_name=meta_name)
    #TODO: Pass in kwargs (Like md5sum, url, etc. that are useful)
    # process_machine_export(machine_export, md5_sum=md5_sum, url=url)
    #TODO: Option to copy this file into iRODS
    #TODO: Option to upload this file into S3 

    logger.debug("machine_export_task task finished at %s." % datetime.now())
    return (md5_sum, url)

@task(name='machine_imaging_task', ignore_result=False)
def machine_imaging_task(create_fn, args, kwargs):
    new_image_id = create_fn(*args, **kwargs)
    return new_image_id
