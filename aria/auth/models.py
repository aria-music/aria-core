from tortoise import Model
from tortoise.fields import ForeignKeyField, ReverseRelation
from tortoise.fields.data import TextField, UUIDField

class User(Model):
    id = UUIDField(pk=True)
    name = TextField(null=True)
    invite = TextField(null=True)
    
    auths = ReverseRelation["Auth"]

    def __str__(self) -> str:
        return f"User(id:{self.id}, invite:{self.invite})"

class Auth(Model):
    # tortoise orm does not support multiple field primary key
    # so currently we use a string that shape is [provider]:[id] as primary key
    id = TextField(pk=True)

    user = ForeignKeyField("models.User", related_name="auths")

class Token(Model):
    token = TextField(pk=True)
