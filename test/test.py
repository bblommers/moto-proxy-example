import boto3
import io
import json
import zipfile
from botocore.config import Config
from uuid import uuid4


url = "http://0.0.0.0:5005"
config = Config(proxies={"https": url})


def test_invoke_lambda_with_proxy():

    dynamodb = boto3.resource("dynamodb", region_name='us-east-1', config=config, verify=False)
    dynamodb.create_table(
        TableName="MyTable",
        KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
        ProvisionedThroughput={"ReadCapacityUnits": 1, "WriteCapacityUnits": 1},
    )

    conn = boto3.client("lambda", region_name='us-east-1', config=config, verify=False)
    function_name = str(uuid4())[0:6]
    conn.create_function(
        FunctionName=function_name,
        Runtime="python3.11",
        Role=get_role_name(),
        Handler="lambda_function.lambda_handler",
        Code={"ZipFile": get_proxy_zip_file()},
        Description="test lambda function",
        Timeout=3,
        MemorySize=128,
        Publish=True,
    )

    json_data = {
        'id': 'value',
        'another_key': 'another_value'
    }
    result = conn.invoke(
        FunctionName=function_name,
        InvocationType="RequestResponse",
        Payload=json.dumps({'body': json.dumps(json_data)}),
    )
    assert result["StatusCode"] == 200

    items = dynamodb.Table('MyTable').scan()["Items"]
    assert items == [{'id': 'value', 'another_key': 'another_value'}]


def get_role_name():
    iam = boto3.client("iam", region_name='us-east-1', config=config, verify=False)
    return iam.create_role(
        RoleName="my-role",
        AssumeRolePolicyDocument="some policy",
        Path="/my-path/",
    )["Role"]["Arn"]


def _process_lambda(func_str):
    zip_output = io.BytesIO()
    zip_file = zipfile.ZipFile(zip_output, "w", zipfile.ZIP_DEFLATED)
    zip_file.writestr("lambda_function.py", func_str)
    zip_file.close()
    zip_output.seek(0)
    return zip_output.read()


def get_proxy_zip_file():
    func_str = """
import boto3
import json

def lambda_handler(event, context):
    dynamodb = boto3.resource('dynamodb', 'us-east-1')
    table = dynamodb.Table('MyTable')

    # Parse the JSON input from the event
    json_data = json.loads(event.get('body'))
    response = table.put_item(Item=json_data)

    # Check the response to confirm successful update
    if response['ResponseMetadata']['HTTPStatusCode'] == 200:
        return {
            'statusCode': 200,
            'body': json.dumps('Data updated successfully')
        }
    else:
        return {
            'statusCode': 500,
            'body': json.dumps('Error updating data')
        }
"""
    return _process_lambda(func_str)
