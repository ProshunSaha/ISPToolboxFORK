from django.contrib.auth.forms import UserCreationForm
from IspToolboxAccounts.models import User, IspToolboxUserSignUpInfo
from django import forms
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm


class IspToolboxUserCreationForm(UserCreationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].help_text = _('Use 8 or more characters with a mix of letters and numbers.')
        self.fields['password2'].help_text = _('Enter the same password as before, for verification.')

    email = forms.EmailField(
                label="Email",
                label_suffix="",
                required=True,
                widget=forms.TextInput(attrs={'placeholder': 'name@company.com'}))
    first_name = forms.CharField(
                label="First Name",
                label_suffix="",
                required=True,
                widget=forms.TextInput(attrs={'placeholder': 'First Name'}))
    last_name = forms.CharField(
                label="Last Name",
                label_suffix="",
                required=True,
                widget=forms.TextInput(attrs={'placeholder': 'Last Name'}))

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ['email', 'first_name', 'last_name']

    error_css_class = "error"
    required_css_class = "required"


class IspToolboxUserAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'name': 'email'
        })
    error_css_class = "error"
    required_css_class = "required"


class IspToolboxUserSignUpInfoForm(forms.ModelForm):
    company_website = forms.URLField(
        label="Company Website",
        label_suffix="",
        required=True,
        error_messages={'required': 'Please enter your company\'s website'},
        widget=forms.TextInput(attrs={'placeholder': 'www.company.com'}))
    individual_role = forms.MultipleChoiceField(
        label="What is your role?",
        label_suffix="",
        required=False,
        widget=forms.CheckboxSelectMultiple,
        choices=IspToolboxUserSignUpInfo.ROLE_CHOICES)
    subscriber_size = forms.ChoiceField(
        label="Subscriber Size",
        label_suffix="",
        required=False,
        widget=forms.Select,
        choices=IspToolboxUserSignUpInfo.SUBSCRIBER_SIZE_CHOICES)
    company_goal = forms.MultipleChoiceField(
        label="What are you business goals this year?",
        label_suffix="",
        required=False,
        widget=forms.CheckboxSelectMultiple,
        choices=IspToolboxUserSignUpInfo.GOAL_CHOICES)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # checkboxes = [
        #     'individual_role', 'company_goal'
        # ]
        # for field in checkboxes:
        #     self.fields[field].modifycheckbox = True

    class Meta:
        model = IspToolboxUserSignUpInfo
        exclude = ('owner',)
        labels = {
        }
        help_texts = {
        }

    field_order = [
        'company_website', 'individual_role', 'subscriber_size', 'company_goal'
    ]
    error_css_class = "error"
    required_css_class = "required"


class IspToolboxUserPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['new_password1'].help_text = _('Use 8 or more characters with a mix of letters and numbers.')
        self.fields['new_password2'].help_text = _('Enter the same password as before, for verification.')


class IspToolboxUserInfoChangeForm(forms.ModelForm):
    class Meta:
        fields = ['email', 'first_name', 'last_name']
        model = User


class IspToolboxUserDeleteAccountForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['confirmation'].help_text = _('Type `permanently delete` to confirm')

    confirmation = forms.CharField(
                required=True,
                widget=forms.TextInput(attrs={'placeholder': 'permanently delete'}))

    def try_delete(self, request):
        valid_input = self.cleaned_data.get('confirmation') == 'permanently delete'
        if valid_input:
            request.user.delete()
            return True
        else:
            self.add_error('confirmation', 'incorrect')
            return False
