#!/bin/bash
mkdir ~/.aws
sudo cp /mnt/efs/fs1/alex/* ~/.aws
sudo chown -R ec2-user:ec2-user ~/.aws
sudo amazon-linux-extras install epel
sudo yum install redis docker
sudo curl -L "https://github.com/docker/compose/releases/download/1.26.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
sudo ln -s /usr/local/bin/docker-compose /usr/bin/docker-compose
sudo systemctl start docker
sudo docker-compose build
sudo docker-compose up -d
