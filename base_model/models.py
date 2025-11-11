from django.db.models import Model, ForeignKey, DateTimeField, SET_NULL, BooleanField

from config.middlewares.current_user import get_current_user_id


class BaseModel(Model):
    """Simply inherit this class to enable soft usage on a model.
    """

    class Meta:
        abstract = True

    created_date = DateTimeField(auto_now_add=True, null=True)
    modified_date = DateTimeField(auto_now=True, null=True)
    created_by = ForeignKey("user.User", null=True, related_name="+", on_delete=SET_NULL)
    modified_by = ForeignKey("user.User", null=True, related_name="+", on_delete=SET_NULL)
    is_active = BooleanField(default=True)

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        self.before_save()
        self.is_new = not self.id
        self.created_by_id = self.created_by_id if self.created_by else get_current_user_id()
        self.modified_by_id = get_current_user_id()
        super(BaseModel, self).save(force_insert, force_update, using, update_fields)
        self.after_save()
        return self

    def before_save(self):
        pass

    def after_save(self):
        pass

    def dict(self):
        return {"id": self.id, "name": str(self)}
