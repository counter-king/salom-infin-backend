import graphene

from apps.reference.graphql.mutations import Mutation
from apps.reference.graphql.queries import Query

schema = graphene.Schema(query=Query, mutation=Mutation)
