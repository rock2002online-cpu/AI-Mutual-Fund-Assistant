from services.nav_service import NAVService

service = NAVService()

df = service.get_nav()

print(df.head())

print(df.columns)