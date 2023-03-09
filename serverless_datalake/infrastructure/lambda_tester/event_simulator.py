import boto3
import json
import datetime
import random

client = boto3.client('events')


def handler(event, context):

    print(f'Event Emitter Sample')

    currencies = ['dollar', 'rupee', 'pound', 'rial']
    locations = ['US-TX', 'US-FL', 'IN-MH', 'IN-GA', 'IN-AP']
    names = ['Adam-O', 'William-W', 'Karma-C', 'Fraser-S', 'Prasad-V', 'Preeti-M', 'David-V', 'Nathan-S']
    sample_json = {
        "amount": {
            "value": 50,
            "currency": "dollar"
        },
        "location": {
            "country": "US",
            "state": "TX",
        },
        "timestamp": "2022-12-31T00:00:00.000Z",
        "firstName": "Rav",
        "lastName": "G"
    }

    for i in range(0, 1000):
        sample_json["amount"]["value"] = random.randint(10, 3200)
        sample_json["amount"]["currency"] = random.choice(currencies)
        location = random.choice(locations).split('-')
        sample_json["location"]["country"] = location[0]
        sample_json["location"]["state"] = location[1]
        name = random.choice(names).split('-')
        sample_json["firstName"] = name[0]
        sample_json["lastName"] = name[1]
        sample_json["timestamp"] = datetime.datetime.utcnow().isoformat()[
            :-3] + 'Z'
        response = client.put_events(
            Entries=[
                {
                    'Time': datetime.datetime.now(),
                    'Source': 'transactions',
                    'DetailType': 'card-event',
                    'Detail': json.dumps(sample_json),
                    'EventBusName': 'serverless-bus-dev'
                },
            ]
        )
        # print(response)
    print('Simulation Complete. Events should be visible in S3 after 2(configured Firehose Buffer time) minutes')
