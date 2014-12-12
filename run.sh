nmap -PN -n -sL $1 | grep report | awk '{print $5}'> ips/$2.ips
sudo ./netmap.py -i ips/$2.ips  -p -vvv
sudo chown -R www-data:www-data ./img/*
sudo chmod 664 ./img/*
dot -Tpng ./img/test.dot -o ./img/$2.png
sudo chown www-data:www-data ./img/*
