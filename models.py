from peewee import *

db = SqliteDatabase('base.db', pragmas={'foreign_keys': 1})


class BaseModel(Model):
    class Meta:
        database = db


class User(BaseModel):
    username = CharField(unique=True)


class Profile(BaseModel):
    owner = ForeignKeyField(User, backref='profiles')
    name = CharField()
    # proxy = CharField()
    phone_number = CharField(max_length=10)
    password = CharField()


class CurrentProfile(BaseModel):
    user = ForeignKeyField(User, unique=True)
    profile = ForeignKeyField(Profile, null=True, on_delete='CASCADE')


if __name__ == '__main__':
    db.connect()
    db.create_tables([User, Profile, CurrentProfile])
