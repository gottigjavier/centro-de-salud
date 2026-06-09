"""Formularios para gestión de usuarios del sistema."""

from django import forms

from .models import User


class SetupAdminForm(forms.ModelForm):
    """Formulario para crear el primer administrador."""

    password1 = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs={"class": "form-input"}),
    )
    password2 = forms.CharField(
        label="Confirmar contraseña",
        widget=forms.PasswordInput(attrs={"class": "form-input"}),
    )

    class Meta:
        model = User
        fields = ["email", "first_name", "last_name", "phone"]
        widgets = {
            "email": forms.EmailInput(attrs={"class": "form-input"}),
            "first_name": forms.TextInput(attrs={"class": "form-input"}),
            "last_name": forms.TextInput(attrs={"class": "form-input"}),
            "phone": forms.TextInput(attrs={"class": "form-input"}),
        }

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Ya existe un usuario con este email.")
        return email

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Las contraseñas no coinciden.")
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        user.role = "admin"
        user.is_staff = True
        user.is_superuser = True
        if commit:
            user.save()
        return user


class UserCreateForm(forms.ModelForm):
    """Formulario para que admin cree otros usuarios."""

    password1 = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs={"class": "form-input"}),
    )
    password2 = forms.CharField(
        label="Confirmar contraseña",
        widget=forms.PasswordInput(attrs={"class": "form-input"}),
    )

    class Meta:
        model = User
        fields = ["email", "first_name", "last_name", "phone", "role"]
        widgets = {
            "email": forms.EmailInput(attrs={"class": "form-input"}),
            "first_name": forms.TextInput(attrs={"class": "form-input"}),
            "last_name": forms.TextInput(attrs={"class": "form-input"}),
            "phone": forms.TextInput(attrs={"class": "form-input"}),
            "role": forms.Select(attrs={"class": "form-input"}),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)
        # Un admin NO puede crear otro admin (solo superuser puede)
        if self.request and not self.request.user.is_superuser:
            self.fields["role"].choices = [
                (k, v)
                for k, v in self.fields["role"].choices
                if k != "admin"
            ]

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Ya existe un usuario con este email.")
        return email

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Las contraseñas no coinciden.")
        return password2

    def clean_role(self):
        role = self.cleaned_data.get("role")
        # Si el usuario logueado no es superuser, no puede crear admins
        if self.request and not self.request.user.is_superuser and role == "admin":
            raise forms.ValidationError(
                "No tienes permisos para crear administradores."
            )
        return role

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        # Si es admin, darle is_staff
        if user.role == "admin":
            user.is_staff = True
        if commit:
            user.save()
        return user


class UserEditForm(forms.ModelForm):
    """Formulario para editar usuarios existentes."""

    class Meta:
        model = User
        fields = ["email", "first_name", "last_name", "phone", "role", "is_active"]
        widgets = {
            "email": forms.EmailInput(attrs={"class": "form-input"}),
            "first_name": forms.TextInput(attrs={"class": "form-input"}),
            "last_name": forms.TextInput(attrs={"class": "form-input"}),
            "phone": forms.TextInput(attrs={"class": "form-input"}),
            "role": forms.Select(attrs={"class": "form-input"}),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)
        if self.request and not self.request.user.is_superuser:
            self.fields["role"].choices = [
                (k, v)
                for k, v in self.fields["role"].choices
                if k != "admin"
            ]

    def clean_role(self):
        role = self.cleaned_data.get("role")
        if self.request and not self.request.user.is_superuser and role == "admin":
            raise forms.ValidationError(
                "No tienes permisos para asignar rol administrador."
            )
        return role
