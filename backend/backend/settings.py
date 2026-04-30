# we import project_settings from the different files in project_setting module based on the environment variable


from decouple import config



APP_ENV = config('APP_ENV', default='development').lower()

if APP_ENV == 'production':
    from project_setting.production import *
elif APP_ENV == 'development':
    from project_setting.development import *
else:
    raise ValueError("Invalid APP_ENV value. Choose from 'production' or 'development'.")






# for reference in the codebase like in emails for reporting issues
ENVIRONMENT = APP_ENV
