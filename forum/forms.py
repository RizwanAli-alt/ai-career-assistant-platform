from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Post, Reply, UserProfile, MentorshipRequest


# ─────────────────────────────────────────────
#  REGISTER FORM
# ─────────────────────────────────────────────
class RegisterForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            "class": "form-control glass-input",
            "placeholder": "your@email.com",
        }),
    )
    first_name = forms.CharField(
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control glass-input",
            "placeholder": "First name (optional)",
        }),
    )

    class Meta:
        model = User
        fields = ("username", "first_name", "email", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Apply glass-input CSS class to all inherited fields
        glass_attrs = {"class": "form-control glass-input"}
        placeholder_map = {
            "username": "Choose a username",
            "password1": "Create a strong password",
            "password2": "Confirm your password",
        }
        for field_name, field in self.fields.items():
            field.widget.attrs.update(glass_attrs)
            if field_name in placeholder_map:
                field.widget.attrs["placeholder"] = placeholder_map[field_name]

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("This email is already registered.")
        return email


# ─────────────────────────────────────────────
#  POST FORM
# ─────────────────────────────────────────────
class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ("title", "category", "body")
        widgets = {
            "title": forms.TextInput(attrs={
                "class": "form-control glass-input",
                "placeholder": "Write a clear, descriptive title (5–150 characters)",
                "maxlength": 150,
            }),
            "category": forms.Select(attrs={
                "class": "form-select glass-input",
            }),
            "body": forms.Textarea(attrs={
                "class": "form-control glass-input",
                "placeholder": "Share your thoughts, questions, or insights... (20–5000 characters)",
                "rows": 8,
                "maxlength": 5000,
            }),
        }
        labels = {
            "title": "Post Title",
            "category": "Category",
            "body": "Content",
        }

    def clean_title(self):
        title = self.cleaned_data.get("title", "").strip()
        if len(title) < 5:
            raise forms.ValidationError("Title must be at least 5 characters.")
        if len(title) > 150:
            raise forms.ValidationError("Title cannot exceed 150 characters.")
        return title

    def clean_body(self):
        body = self.cleaned_data.get("body", "").strip()
        if len(body) < 20:
            raise forms.ValidationError("Post body must be at least 20 characters.")
        if len(body) > 5000:
            raise forms.ValidationError("Post body cannot exceed 5000 characters.")
        return body


# ─────────────────────────────────────────────
#  REPLY FORM
# ─────────────────────────────────────────────
class ReplyForm(forms.ModelForm):
    class Meta:
        model = Reply
        fields = ("body",)
        widgets = {
            "body": forms.Textarea(attrs={
                "class": "form-control glass-input",
                "placeholder": "Write a helpful reply...",
                "rows": 4,
                "maxlength": 2000,
            }),
        }
        labels = {
            "body": "",   # Label hidden — placeholder does the job
        }

    def clean_body(self):
        body = self.cleaned_data.get("body", "").strip()
        if len(body) < 5:
            raise forms.ValidationError("Reply must be at least 5 characters.")
        if len(body) > 2000:
            raise forms.ValidationError("Reply cannot exceed 2000 characters.")
        return body


# ─────────────────────────────────────────────
#  PROFILE EDIT FORM
# ─────────────────────────────────────────────
class ProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ("role", "bio", "avatar", "linkedin_url", "github_url")
        widgets = {
            "role": forms.Select(attrs={
                "class": "form-select glass-input",
            }),
            "bio": forms.Textarea(attrs={
                "class": "form-control glass-input",
                "placeholder": "Tell the community about yourself...",
                "rows": 4,
                "maxlength": 500,
            }),
            "avatar": forms.FileInput(attrs={
                "class": "form-control glass-input",
                "accept": "image/*",
            }),
            "linkedin_url": forms.URLInput(attrs={
                "class": "form-control glass-input",
                "placeholder": "https://linkedin.com/in/your-profile",
            }),
            "github_url": forms.URLInput(attrs={
                "class": "form-control glass-input",
                "placeholder": "https://github.com/your-username",
            }),
        }
        labels = {
            "role": "I am a...",
            "bio": "Bio",
            "avatar": "Profile Picture",
            "linkedin_url": "LinkedIn URL",
            "github_url": "GitHub URL",
        }

    def clean_bio(self):
        bio = self.cleaned_data.get("bio", "").strip()
        if len(bio) > 500:
            raise forms.ValidationError("Bio cannot exceed 500 characters.")
        return bio

    def clean_avatar(self):
        avatar = self.cleaned_data.get("avatar")
        if avatar:
            # Limit file size to 2MB
            if avatar.size > 2 * 1024 * 1024:
                raise forms.ValidationError("Avatar image must be under 2MB.")
            # Only allow image types
            allowed_types = ["image/jpeg", "image/png", "image/webp", "image/gif"]
            if hasattr(avatar, "content_type") and avatar.content_type not in allowed_types:
                raise forms.ValidationError("Only JPEG, PNG, WebP, or GIF images are allowed.")
        return avatar


# ─────────────────────────────────────────────
#  MENTORSHIP REQUEST FORM
# ─────────────────────────────────────────────
class MentorshipRequestForm(forms.ModelForm):
    class Meta:
        model = MentorshipRequest
        fields = ("message",)
        widgets = {
            "message": forms.Textarea(attrs={
                "class": "form-control glass-input",
                "placeholder": (
                    "Introduce yourself and explain what kind of mentorship or guidance "
                    "you're looking for... (min 20 characters)"
                ),
                "rows": 5,
                "maxlength": 1000,
            }),
        }
        labels = {
            "message": "Your Message",
        }

    def clean_message(self):
        message = self.cleaned_data.get("message", "").strip()
        if len(message) < 20:
            raise forms.ValidationError("Message must be at least 20 characters.")
        if len(message) > 1000:
            raise forms.ValidationError("Message cannot exceed 1000 characters.")
        return message