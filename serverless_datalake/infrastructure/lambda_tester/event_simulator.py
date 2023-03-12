import boto3
import json
import datetime
import random

client = boto3.client('events')


def handler(event, context):

    print(f'Event Emitter Sample')

    currencies = ['dollar', 'rupee', 'pound', 'rial']
    locations = ['US-TX-alto road, T4 serein', 'US-FL-palo road, lake view', 'IN-MH-cira street, Sector 17 Vashi', 'IN-GA-MG Road, Sector 25 Navi', 'IN-AP-SB Road, Sector 10 Mokl']
    # First name , Last name, Credit card number
    names = ['Adam-Oldham-4024007175687564', 'William-Wong-4250653376577248', 'Karma-Chako-4532695203170069', 'Fraser-Sequeira-376442558724183', 'Prasad-Vedhantham-340657673453698', 'Preeti-Mathias-5247358584639920', 'David-Valles-5409458579753902', 'Nathan-S-374420227894977', 'Sanjay-C-374549020453175', 'Vikas-K-3661894701348823']
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
        sample_json["amount"]["value"] = random.randint(10, 5000)
        sample_json["amount"]["currency"] = random.choice(currencies)
        location = random.choice(locations).split('-')
        sample_json["location"]["country"] = location[0]
        sample_json["location"]["state"] = location[1]
        sample_json["location"]["city"] = location[2]
        name = random.choice(names).split('-')
        sample_json["firstName"] = name[0]
        sample_json["lastName"] = name[1]
        sample_json["credit_card"] = name[2]
        sample_json["transaction_message"] = name[0] + ' with credit card number ' + name[2] + ' made a purchase of ' + sample_json["amount"]["currency"] + '. Residing at ' + location[2] + ',' + location[1] + ', ' + location[0] + '.'
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
        
        #print(response)
    print('Simulation Complete. Events should be visible in S3 after 2(configured Firehose Buffer time) minutes')
