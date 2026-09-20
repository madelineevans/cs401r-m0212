## ADR-001: NorthStar Platform Foundation

### Status

Accepted

### Context

NorthStar is an outdoors and home-goods selling company with 2.1M customers worth about $3.2B.
This has a shared AI platform to collect, analyse, and make use of customer data to better
grow the company and make larger scale business decisions. As such, it needs an identity model
to control who has access to the AI and secure it and ensure privacy, and a storage tier to
be able to save all this data so it can be used and trained with.

### Decision

NorthStar uses one VPC in us-east-1 with CIDR 10.0.0.0/16, a public subnet of 10.0.100.0/24 in us-east-1a, that is connected via a public route table to the internet gateway. This setup is nice because it is intentionally small to start which makes it highly configurable and a good base to work from while we figure out the churn-scoring, while still providing space or room to add more subnets or zones or other things when we continue to grow.
As for the S3 prefix design, having the 4 prefixes be separate prefixes rather than separate buckets within a SSE-S3 encrypted bucket because the 3 sources share one ML flow, so moving data between the buckets is highly likely and costly. Having them in the same place decreases that as well as provides ease of access.
The IAM role model also trusts Sagemaker, and allows us to do many actions within that realm without embedding credentials in the code or anything of the sort.

### Consequences

#### What this makes easy

The 4-prefix layout give the sources a shared place to put information, it is simpler and closely connected. This makes it easy for a churn pipeline to connect the various prefixes. Having one subnet and zone and all is also a lot more simple to manage and deal with.

#### What this makes harder

Just having sone subnet in one availibilty zone is not the smartest decision ever, because if that zone failed it would affect the entire system and cause a lot of issues everywhere if that one zone were to experience issues.

#### What would cause you to revisit this decision

This would be something to revisit and reevaluate if we grow large enough that having multiple zones is a valid concern or we are concerned enough about issues in one zone to want to have a backup or several. We should also revisit the storage system when or if the need of easy data transferance is outweighed by the need to have separate access restrictionst to the various buckets for users.

### Alternative Considered

One alternative would be to have each prefix be a bucket instead. That would isolate the data types and stages and provide specific access restrictions to them. However, this would be more costly for the transferance of data so it's simply not worth it to us right now

### AWS Service Selection

- Networking isolation model: The current setup provides the smallest possible working setup we can have for Lab 1 and the sagemaker domain while still allowing for future growth.
- Storage design: This bucket and prefix system is great for the raw to artifact lifecycle that our data is going to undergo.
- Identity model: IAM provides a way to grant needed SageMaker access without embedding credentials or giving everyone access.
- ML development environment: Sagemaker domain and user profile gives us a place to explore data and build models and LLM's.
