from django.contrib.auth.password_validation import CommonPasswordValidator
from django.core.exceptions import ValidationError
import re
import os
import logging

logger = logging.getLogger(__name__)


# for password complexity validation
symbols = r'!@#$%^&*(),".?:|<>/-'
class PasswordComplexityValidator:
    def __init__(self, require_uppercase=True, require_lowercase=True, require_digit=True, require_special=True):
        self.require_uppercase = require_uppercase
        self.require_lowercase = require_lowercase
        self.require_digit = require_digit
        self.require_special = require_special

    def validate(self, password, user=None):
        if self.require_uppercase and not re.search(r'[A-Z]', password):
            raise ValidationError("The password must contain at least one uppercase letter.")
        if self.require_lowercase and not re.search(r'[a-z]', password):
            raise ValidationError("The password must contain at least one lowercase letter.")
        if self.require_digit and not re.search(r'[0-9]', password):
            raise ValidationError("The password must contain at least one digit.")
        if self.require_special and not re.search(f'[{re.escape(symbols)}]', password):
            raise ValidationError(f"The password must contain at least one of these special characters: {symbols}.")

    def get_help_text(self):
        text = "Your password must contain:"
        if self.require_uppercase:
            text += " at least one uppercase letter,"
        if self.require_lowercase:
            text += " at least one lowercase letter,"
        if self.require_digit:
            text += " at least one digit,"
        if self.require_special:
            text += " and at least one special character."
        return text.strip(",")
    

# for common password validation
class CustomCommonPasswordValidator(CommonPasswordValidator):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        try:
            file_path = os.path.join(os.path.dirname(__file__), "passwords", "common_password.txt")  # Relative path
            with open(file_path, "r") as f: # fallback to file
                self.common_passwords = [line.strip().lower() for line in f]
        except FileNotFoundError:
            self.common_passwords = ['password', '123456', 'qwerty', 'admin']
            logger.warning(f"common_password.txt not found at {file_path}. Using default list.")            


    def validate(self, password, user=None):
        super().validate(password, user)  # Call the original validator

        if password.lower() in self.common_passwords:
            raise ValidationError(f"Please choose a stronger password. Avoid common passwords.")