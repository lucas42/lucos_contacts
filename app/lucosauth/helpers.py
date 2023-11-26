from lucosauth.models import ApiUser
import random
import string

def new_api_key():
	letters = string.ascii_lowercase
	return ''.join(random.choice(letters) for i in range(20))

def get_calendar_key():
	user, created = ApiUser.objects.get_or_create(system="external_calendar",defaults={'apikey':new_api_key})
	if created:
		print("Created new API User for External Calendar")
	return user.apikey