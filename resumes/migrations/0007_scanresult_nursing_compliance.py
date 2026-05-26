from django.db import migrations, models


class Migration(migrations.Migration):
    """Add nursing_compliance JSONField to ScanResult for travel nursing QA checks."""

    dependencies = [
        ('resumes', '0006_remove_scanresult_document_quality_label_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='scanresult',
            name='nursing_compliance',
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text='Nursing-specific compliance check results (license, certs, sanctions, etc.)',
            ),
        ),
    ]
