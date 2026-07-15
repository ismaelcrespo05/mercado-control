from django import template

register = template.Library()


@register.filter
def has_group(user, group_name):
    """Devuelve True si el usuario pertenece al grupo indicado."""
    if user is None:
        return False
    if not hasattr(user, 'groups'):
        return False
    return user.groups.filter(name=group_name).exists()
