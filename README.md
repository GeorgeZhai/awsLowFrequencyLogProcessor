awsLowFrequencyLogProcessor


awsLowFrequencyLogProcessor is a lambda function to provide enhanced function for alarm notification.

out-of-box aws cloudwatch alarm function is limited, For less frequencly updated system/application logs, awscloudwatch native alarms will enter insuficient data state, and when triggered, It doesn't provide much useful information for fast diagnostic

Adding this lambda function (Python2.7 inline-code) as a subscriber to the loggroups can provide:
	1. Regex based triggering.
	2. 100(default) lines of related logs in email notification
	3. upto 300 (default) chars error logs in the SMS notification
	4. include instance NameTag and private IP in the notifications.


This function can be used with SNS and Cloudwatch Log

License

See the LICENSE file for license rights and limitations (MIT).