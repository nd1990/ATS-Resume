from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('resumes', '0004_add_scan_run_scan_result'),
    ]

    operations = [
        migrations.AddField(
            model_name='scanrun',
            name='jd_title',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Friendly JD / role name for grouping',
                max_length=255,
            ),
        ),
    ]
