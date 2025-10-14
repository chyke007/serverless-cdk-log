# SQS Stack module
from aws_cdk import (
    aws_sqs as sqs,
    aws_iam as iam,
    Stack,
    Duration
)
from constructs import Construct

class SqsStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # Create DLQ separately so we can reference its ARN
        self.message_dlq = sqs.Queue(
            self, "LoggerAppMessageQueueDLQ",
            queue_name="logger-app-messages-dlq",
            retention_period=Duration.days(14)
        )

        # Create SQS Queue for message processing
        self.message_queue = sqs.Queue(
            self, "LoggerAppMessageQueue",
            queue_name="logger-app-messages",
            visibility_timeout=Duration.seconds(30),
            retention_period=Duration.days(14),
            receive_message_wait_time=Duration.seconds(20),  # Long polling
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=3,
                queue=self.message_dlq
            )
        )
