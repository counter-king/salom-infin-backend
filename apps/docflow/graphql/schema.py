import graphene

from apps.docflow.graphql.queries import Query

schema = graphene.Schema(query=Query)
