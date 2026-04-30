from rest_framework import serializers
from authApi.models import User
from django.contrib.auth.password_validation import validate_password
from authApi.validators import PasswordComplexityValidator, CustomCommonPasswordValidator
from django.core.exceptions import ValidationError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
import re
from django.conf import settings


class SignUpSerializer(serializers.ModelSerializer):
    confirm_password = serializers.CharField(write_only=True, min_length=8, required=True)
    signup_code = serializers.CharField(write_only=True)  # Field for signup code

    class Meta:
        model = User
        fields = ['email', 'username', 'password', 'confirm_password', 'first_name', 'last_name', 'designation_number', 'is_driver', 'is_manager', 'signup_code']
        extra_kwargs = {
            'password': {'write_only': True, 'min_length': 8},
        }

    def validate_password(self, password):
        """
        Validate the password using global validators and custom validators.
        """
        try:
            # Apply global validators
            validate_password(password)
        except ValidationError as e:
            raise serializers.ValidationError({'password': e.messages})

        # Apply custom validators
        PasswordComplexityValidator().validate(password)
        CustomCommonPasswordValidator().validate(password)

        return password
    
    def validate_designation_number(self, value):
        """
        Validate that the designation number is unique if provided.
        """
        if value and User.objects.filter(designation_number__iexact=value).exists():
            raise serializers.ValidationError("This designation number is already in use.")
        return value
    
    def validate_username(self, value):
        """
        Validate that the username is unique.
        """
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("This username is not available.")
        return value
    
    def validate(self, data):
        """
        Perform object-level validation.
        """
        password = data.get('password')
        confirm_password = data.get('confirm_password')
        signup_code = data.get('signup_code')

        # Validate signup code
        if signup_code != settings.REG_CODE:
            raise serializers.ValidationError({"signup_code": "Invalid signup code."})

        if password != confirm_password:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})

        # Validate the password explicitly
        self.validate_password(data.get('password'))

        # Validate full name uniqueness
        first_name = data.get('first_name')
        last_name = data.get('last_name')

        if User.objects.filter(
            first_name__iexact=first_name,
            last_name__iexact=last_name
        ).exists():
            raise serializers.ValidationError({
                "name": "This name combination is not available."
            })

        # Prevent users from being both a tenant and a subuser
        if data.get('is_manager') and data.get('is_driver'):
            raise serializers.ValidationError("A user cannot be both a manager and a driver .")

        return data

    def create(self, validated_data):
        validated_data.pop('confirm_password') 
        validated_data.pop('signup_code')

        user = User(**validated_data)
        user.set_password(validated_data['password'])  # Hash password

        try:
            user.save()
        except ValidationError as e:
            # Convert Django ValidationError to DRF ValidationError with detailed message
            raise serializers.ValidationError(str(e))
            
        return user
    

# for user login
class LogInSerializer(TokenObtainPairSerializer):
    email = serializers.EmailField(required=True)

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['email'] = user.email

        return token

    class Meta:
        model = User
        fields = ['email', 'password']

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        if email and password:
            try:
                # Use case-insensitive lookup with iexact
                user = User.objects.get(email__iexact=email)
            except User.DoesNotExist:
                raise serializers.ValidationError('Incorrect details.')

            if not user.check_password(password):
                raise serializers.ValidationError('Incorrect details.')
            
            attrs['user'] = user
        else:
            raise serializers.ValidationError('Both email and password are required.')

        return attrs
    


class UserProfileSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = ['email', 'username', 'first_name', 'last_name', 'designation_number', 'is_driver', 'is_manager']
        read_only_fields = ['email']  # Email is read-only to prevent changes

    def validate_designation_number(self, value):
        """
        Validate that the designation number is unique if provided.
        """
        if value and User.objects.filter(designation_number__iexact=value).exists():
            raise serializers.ValidationError("This designation number is already in use.")
        return value
    
    def validate_username(self, value):
        """
        Validate that the username is unique.
        """
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("This username is not available.")
        return value
    
    def validate(self, data):
        # Prevent users from being both a tenant and a subuser
        if data.get('is_manager') and data.get('is_driver'):
            raise serializers.ValidationError("A user cannot be both a manager and a driver .")
        
        # Validate full name uniqueness if either first_name or last_name is being updated
        first_name = data.get('first_name', self.instance.first_name)
        last_name = data.get('last_name', self.instance.last_name)

        if User.objects.filter(
            first_name__iexact=first_name,
            last_name__iexact=last_name
        ).exclude(pk=self.instance.pk).exists():
            raise serializers.ValidationError({
                "name": "This name combination is not available."
            })

        return data

    def update(self, instance, validated_data):
        # Prevent email updates
        if 'email' in validated_data:
            raise serializers.ValidationError("Email cannot be updated.")
        
        return super().update(instance, validated_data)
    

class PasswordResetSerializer(serializers.Serializer):
    new_password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True, min_length=8)

    def validate_new_password(self, password):
        """
        Validate the new password using global validators and custom validators.
        """
        try:
            # Apply global validators
            validate_password(password)
        except ValidationError as e:
            raise serializers.ValidationError({'new_password': e.messages})

        # Apply custom validators
        PasswordComplexityValidator().validate(password)
        CustomCommonPasswordValidator().validate(password)

        return password
    
    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise ValidationError("Passwords do not match.")
        
        password = data['new_password']
        if not re.search(r'[A-Za-z]', password) or not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            raise serializers.ValidationError({
                'new_password': 'Password must contain at least one letter and one symbol.'
            })
        
        # Validate the new password
        self.validate_new_password(data['new_password'])

        return data
    


class EmailChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(
        style={'input_type': 'password'},
        write_only=True,
        required=True
    )
    new_email = serializers.EmailField(required=True)

    def validate_new_email(self, value):
        """Validate that the new email is not already in use."""
        user = self.context.get('request').user
        
        # Don't validate if it's the same email (case-insensitive)
        if user.email.lower() == value.lower():
            raise serializers.ValidationError("New email must be different from current email.")
        
        # Check if email already exists for another user (case-insensitive)
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("This email is already in use.")
        
        return value

    def validate_current_password(self, value):
        """Validate that the current password is correct."""
        user = self.context.get('request').user
        
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        
        return value
    
    def create(self, validated_data):
        """Not used for this serializer."""
        pass
    
    def update(self, instance, validated_data):
        """Not used for this serializer."""
        pass