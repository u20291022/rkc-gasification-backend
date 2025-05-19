from tortoise import fields, models
from tortoise.contrib.postgres.fields import ArrayField


# Модели для Газификации
class Municipality(models.Model):
    """Модель для хранения муниципалитетов"""
    id = fields.IntField(primary_key=True)
    name = fields.CharField(max_length=128, null=False)
    down_parent_id = fields.IntField(null=True)
    tip = fields.IntField(null=False)  # Только где tip = 2
    id_parent = fields.IntField(null=True)
    path_id = ArrayField(null=False)
    level_parent = fields.IntField(null=False)
    
    class Meta:
        schema = "sp_s_subekty"
        table = "v_all_name_mo" # Используем представление из схемы sp_s_subekty


class AddressV2(models.Model):
    """Модель для адресов"""
    id = fields.IntField(primary_key=True)
    id_mo = fields.IntField(null=True)
    district = fields.CharField(max_length=128, null=True)
    city = fields.CharField(max_length=128, null=True)
    street = fields.CharField(max_length=128, null=True)
    house = fields.CharField(max_length=64, null=True)
    flat = fields.CharField(max_length=64, null=True)
    id_parent = fields.IntField(null=True)
    mkd = fields.BooleanField(default=False)
    is_mobile = fields.BooleanField(default=False)
    
    class Meta:
        schema = "s_gazifikacia"
        table = "t_address_v2"


class TypeValue(models.Model):
    """Модель для типов значений"""
    id = fields.IntField(primary_key=True)
    type_value = fields.CharField(max_length=128, null=True)
    for_mobile = fields.BooleanField()

    class Meta:
        schema = "s_gazifikacia"
        table = "t_type_value"


class GazificationData(models.Model):
    """Модель для данных о газификации"""
    id = fields.IntField(primary_key=True)
    id_address = fields.IntField()
    id_type_address = fields.IntField(null=False)  # 3 - подключены к газу, 4 - не подключены
    id_type_value = fields.IntField(null=True)
    value = fields.CharField(max_length=256, null=True)  # true/false или текст
    date_doc = fields.DateField(null=True)
    date = fields.DateField(null=True)
    
    class Meta:
        schema = "s_gazifikacia"
        table = "t_gazifikacia_data"
