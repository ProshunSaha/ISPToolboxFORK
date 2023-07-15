# Production Load Balancer
resource "aws_lb" "production" {
  name               = "${var.ecs_cluster_name}-alb"
  load_balancer_type = "application"
  internal           = false
  security_groups    = [aws_security_group.load-balancer.id]
  subnets            = [aws_subnet.public-subnet-1.id, aws_subnet.public-subnet-2.id]
}

# Target group
resource "aws_alb_target_group" "default-target-group" {
  name     = "${var.ecs_cluster_name}-tg"
  port     = 80
  protocol = "HTTP"
  vpc_id   = aws_vpc.production-vpc.id

  health_check {
    path                = var.health_check_path
    port                = "traffic-port"
    healthy_threshold   = 5
    unhealthy_threshold = 2
    timeout             = 2
    interval            = 5
    matcher             = "200"
  }
}

resource "aws_acm_certificate" "cert" {
  domain_name       = "*.fbctower.com"
  subject_alternative_names  = ["fbctower.com"]
  validation_method = "DNS"

  tags = {
    Name = "isptoolbox_acm_certificate-cert"
  }

  lifecycle {
    create_before_destroy = true
  }
}

# Listener (redirects traffic from the load balancer to the target group)
resource "aws_alb_listener" "ecs-alb-http-listener" {
  load_balancer_arn = aws_lb.production.id
  port              = "443"
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-2016-08"
  certificate_arn   = aws_acm_certificate.cert.arn
  depends_on        = [aws_alb_target_group.default-target-group]

  default_action {
    type             = "forward"
    target_group_arn = aws_alb_target_group.default-target-group.arn
  }
}

resource "aws_alb_listener" "http" {
  load_balancer_arn = aws_lb.production.id
  port              = 80
  protocol          = "HTTP"

  default_action {
    target_group_arn = aws_alb_target_group.default-target-group.arn
    type             = "forward"
  }
}