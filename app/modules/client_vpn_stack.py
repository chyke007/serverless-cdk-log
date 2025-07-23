from aws_cdk import (
    aws_ec2 as ec2,
    Stack,
    CfnOutput
)
from constructs import Construct

class ClientVpnStack(Stack):
    def __init__(self, scope: Construct, id: str, vpc: ec2.Vpc, client_vpn_sg,  **kwargs):
        super().__init__(scope, id, **kwargs)

        # Context values for certificates
        server_cert_arn = self.node.try_get_context("vpn_server_cert_arn") or "arn:aws:acm:REGION:ACCOUNT:certificate/SERVER_CERT_ID"
        client_cert_arn = self.node.try_get_context("vpn_client_cert_arn") or "arn:aws:acm:REGION:ACCOUNT:certificate/CLIENT_CERT_ID"

        # ✅ Client VPN Endpoint
        self.client_vpn = ec2.CfnClientVpnEndpoint(
            self, "ClientVpnEndpoint",
            authentication_options=[{
                "type": "certificate-authentication",
                "mutualAuthentication": {
                    "clientRootCertificateChainArn": client_cert_arn
                }
            }],
            client_cidr_block="10.100.0.0/16",
            connection_log_options={"enabled": False},
            server_certificate_arn=server_cert_arn,
            vpc_id=vpc.vpc_id,
            security_group_ids=[client_vpn_sg.security_group_id],
            split_tunnel=True,
            # Uses VPC DNS so internal Route53 works
            dns_servers=["10.0.0.2"],
            description="Client VPN for secure VPC access"
        )

        # ✅ Associate VPN with private subnets
        for i, subnet in enumerate(vpc.select_subnets(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS).subnets):
            assoc = ec2.CfnClientVpnTargetNetworkAssociation(
                self, f"ClientVpnAssoc{i}",
                client_vpn_endpoint_id=self.client_vpn.ref,
                subnet_id=subnet.subnet_id
            )
        
        # ✅ Authorization rule: allow all users (for now)
        ec2.CfnClientVpnAuthorizationRule(
            self, "ClientVpnAuthRule",
            client_vpn_endpoint_id=self.client_vpn.ref,
            target_network_cidr=vpc.vpc_cidr_block,
            authorize_all_groups=True
        )

        CfnOutput(self, "ClientVpnEndpointId", value=self.client_vpn.ref, description="Client VPN Endpoint ID")
