from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("productos", "0007_producto_revisado_producto_revisado_por"),
    ]

    operations = [
        migrations.AddField(
            model_name="producto",
            name="codigo_tipo",
            field=models.CharField(
                blank=True,
                default="",
                max_length=20,
                verbose_name="Formato del código de barras",
            ),
        ),
    ]