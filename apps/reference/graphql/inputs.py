import graphene


class CorrespondentInput(graphene.InputObjectType):
    address = graphene.String(required=False)
    birth_date = graphene.Date(required=False)
    checkpoint = graphene.String(required=False)
    description = graphene.String(required=False)
    email = graphene.String(required=False)
    father_name = graphene.String(required=False)
    first_name = graphene.String(required=False)
    gender = graphene.String(required=False)
    last_name = graphene.String(required=False)
    legal_address = graphene.String(required=False)
    legal_name = graphene.String(required=False)
    name = graphene.String(required=False)
    phone = graphene.String(required=False)
    tin = graphene.String(required=False)
    type = graphene.String(required=True)

    def validate(self, *args, **kwargs):
        input_type = self.type
        required_fields = {
            "legal": ["name", "tin", "legal_name", "legal_address", "phone", "description"],
            "physical": ["first_name", "last_name", "father_name", "phone", "address", "gender"],
        }

        if input_type not in required_fields:
            raise ValueError(f"Invalid 'type' value: {input_type}")

        for req_field in required_fields[input_type]:
            if not getattr(self, req_field):
                raise ValueError(f"{req_field} is required when type is '{input_type}'.")
