import json
import logging
import os
from datetime import datetime

import boto3

LOG = logging.getLogger("map-to-s3-lambda")


def lambda_handler(event, context):
    _ = context

    # This AWS Lambda function must be deployed with DB_TABLE_NAME and
    # DB_TABLE_REGION environment variables
    table_name = os.getenv("DB_TABLE_NAME")
    table_region = os.getenv("DB_TABLE_REGION")

    # Get uri from origin request event
    request = event["Records"][0]["cf"]["request"]
    web_uri = request["uri"]

    # Query latest item with matching uri from DynamoDB table
    LOG.info("Querying '%s' table for '%s'...", table_name, web_uri)

    query_result = boto3.client("dynamodb", region_name=table_region).query(
        TableName=table_name,
        Limit=1,
        ScanIndexForward=False,
        KeyConditionExpression="web_uri = :u and from_date <= :d",
        ExpressionAttributeValues={
            ":u": {"S": web_uri},
            ":d": {"S": str(datetime.utcnow())},
        },
    )

    if query_result["Items"]:
        LOG.info("Item found for '%s'", web_uri)

        # Update request uri to point to S3 object key
        latest_item = query_result["Items"][0]

        try:
            request["uri"] = latest_item["object_key"]["S"]
            return request
        except KeyError:
            err_msg = "No 'object_key' found in %s", json.dumps(latest_item)
            LOG.error(err_msg)
            return {
                "status": "500",
                "statusDescription": "Internal Server Error",
                "body": json.dumps({"error": err_msg})
            }
    else:
        LOG.info("No item for '%s'", web_uri)

        # Report 404 to prevent attempts on S3
        return {
            "status": "404",
            "statusDescription": "Not Found",
        }
