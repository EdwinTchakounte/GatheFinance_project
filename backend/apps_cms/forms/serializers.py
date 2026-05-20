from rest_framework import serializers

from .captcha import verify as verify_captcha
from .models import ContactSubmission, NewsletterSubscriber

LANG_CHOICES = ("fr", "en")


class _AntiSpamMixin(serializers.Serializer):
    # Honeypot — must stay empty. Real users never see it.
    website = serializers.CharField(required=False, allow_blank=True, write_only=True)
    captcha_token = serializers.CharField(write_only=True)
    captcha_answer = serializers.CharField(write_only=True)
    language = serializers.ChoiceField(choices=LANG_CHOICES, default="fr")

    def validate(self, attrs):
        if attrs.get("website"):
            # Silent rejection handled in the view; flag it here.
            self.context["honeypot_tripped"] = True
        if not verify_captcha(attrs.get("captcha_token", ""), attrs.get("captcha_answer", "")):
            raise serializers.ValidationError({"captcha_answer": "Réponse incorrecte. Merci de réessayer."})
        return attrs

    def _strip_meta(self, validated):
        for key in ("website", "captcha_token", "captcha_answer"):
            validated.pop(key, None)
        return validated


class ContactSerializer(_AntiSpamMixin):
    name = serializers.CharField(max_length=200)
    city = serializers.CharField(max_length=160, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=40, required=False, allow_blank=True)
    email = serializers.EmailField()
    message = serializers.CharField(allow_blank=True, required=False)

    def create(self, validated_data):
        data = self._strip_meta(dict(validated_data))
        return ContactSubmission.objects.create(**data, **self.context.get("request_meta", {}))


class NewsletterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    language = serializers.ChoiceField(choices=LANG_CHOICES, default="fr")
    consent = serializers.BooleanField(default=True)
    source = serializers.CharField(max_length=120, required=False, allow_blank=True)
    website = serializers.CharField(required=False, allow_blank=True, write_only=True)

    def validate(self, attrs):
        if attrs.get("website"):
            self.context["honeypot_tripped"] = True
        return attrs

    def create(self, validated_data):
        validated_data.pop("website", None)
        obj, _created = NewsletterSubscriber.objects.update_or_create(
            email=validated_data["email"],
            defaults={
                "language": validated_data.get("language", "fr"),
                "consent": validated_data.get("consent", True),
                "source": validated_data.get("source", ""),
                "is_active": True,
            },
        )
        return obj
