import graphene
from main.schema import Mutation

class Query(graphene.ObjectType):
    pass  # Bu yerda boshqa GraphQL querylarni qo'shishingiz mumkin

schema = graphene.Schema(query=Query, mutation=Mutation)
