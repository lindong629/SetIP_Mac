#!/usr/bin/env python 
# -*- coding: utf-8 -*- 
# Jimmy Lin
import os
import time
import click
from subprocess import Popen, PIPE, call

interface_list = []
com_ip_list = ["192.168.101.233", "255.255.255.0", "192.168.101.1", "114.114.114.114 8.8.8.8"]


def show_menu():
    """显示菜单

    :return:
    """
    print("欢迎使用IP管理系统For MacOS".center(50, "-"))
    for i in ["1、查看网卡信息", "0、退出系统"]:
        print(i)
    print("当前版本V1.0 by Python3".center(50, "-"))
    print("博客 https://blog.rtwork.win ".center(50, "-"))


def show_interface_list():
    """查看网卡信息
    1、show_interface_str 执行命令获取网卡列表
    2、network_name_str 结果由二进制转换为str
    3、network_name_str_list 分割字符串以循环打印
    """
    show_interface_str = Popen("networksetup -listallnetworkservices | awk 'NR == 1 {next} {print $1}'",
                               stdin=None, stdout=PIPE, shell=True)
    network_name_str = str(show_interface_str.communicate()[0], encoding="utf8")
    network_name_str_list = network_name_str.rstrip().split("\n")
    for i in network_name_str_list:
        if i not in interface_list:
            interface_list.append(i)
    print("网卡信息如下：".center(50, "="))
    print("序号\t\t名称")

    interface_list_num = 0
    for i in interface_list:
        print("%s\t\t%s" % (interface_list_num, i))
        interface_list_num += 1
    # 调用需要执行的动作
    action()


def show_interface_ip(interface_name):
    """查看网卡ip

    :return:
    """
    show_interface_ip_str = Popen("networksetup -getinfo %s" % interface_name,
                                  stdin=None, stdout=PIPE, shell=True)
    show_interface_dns_str = Popen("networksetup -getdnsservers %s" % interface_name,
                                   stdin=None, stdout=PIPE, shell=True)
    network_ip_str = str(show_interface_ip_str.communicate()[0], encoding="utf8")
    network_dn_str = str(show_interface_dns_str.communicate()[0], encoding="utf8")
    print("您的【%s】网卡IP如下：".center(50, "=") % interface_name)
    print(network_ip_str)
    print("您的【%s】网卡DNS Server如下：".center(50, "=") % interface_name)
    print(network_dn_str)


def change_interface_ip(name, ip, netmask, gateway, dns):
    """修改网卡信息

    :return:
    """
    set_ip_str = Popen("networksetup -setmanual %s %s %s %s" % (name, ip, netmask, gateway),
                       stdin=None, stdout=PIPE, shell=True)
    set_dns_str = Popen("networksetup -setdnsservers %s %s" % (name, dns),
                        stdin=None, stdout=PIPE, shell=True)
    time.sleep(3)
    show_interface_ip(name)


def change_interface_dhcp(name):
    """设置网卡IP自动获取

    :return:
    """
    set_ip_str = Popen("networksetup -setdhcp %s" % name,
                       stdin=None, stdout=PIPE, shell=True)
    set_dns_str = Popen("networksetup -setdnsservers %s empty" % name,
                        stdin=None, stdout=PIPE, shell=True)
    time.sleep(3)
    show_interface_ip(name)


def action():
    print("请选择您要操作的网卡：".center(50, "="))
    name_input_str = int(input("请输入网卡序号："))

    if len(interface_list) > 0:
        user_c_str = input("是否显示当前网卡配置信息y/n: ")

        if user_c_str == "y":
            show_interface_ip(interface_list[name_input_str])
            user_c_str = input("是否修改y/n: ")
            if user_c_str == "y":
                user_c_str = input("【1】DHCP 【2】手动添加【3】列表预设【0】退出 : ")
                if user_c_str == "1":
                    change_interface_dhcp(interface_list[name_input_str])
                elif user_c_str == "2":
                    change_interface_ip(interface_list[name_input_str],
                                        click.prompt("请输入IP：", default="192.168.1.233"),
                                        click.prompt("请输入Mask：", default="255.255.255.0"),
                                        click.prompt("请输入Gateway：", default="192.168.1.1"),
                                        click.prompt("请输入DNS：", default="114.114.114.114 8.8.8.8"))
                elif user_c_str == "3":
                    change_interface_ip(interface_list[name_input_str],
                                        com_ip_list[0],
                                        com_ip_list[1],
                                        com_ip_list[2],
                                        com_ip_list[3])

        elif user_c_str == "n":
            user_c_str = input("【1】DHCP 【2】手动添加【3】列表预设【0】退出 : ")
            if user_c_str == "1":
                change_interface_dhcp(interface_list[name_input_str])
            elif user_c_str == "2":
                change_interface_ip(interface_list[name_input_str],
                                    click.prompt("请输入IP：", default="192.168.1.233"),
                                    click.prompt("请输入Mask：", default="255.255.255.0"),
                                    click.prompt("请输入Gateway：", default="192.168.1.1"),
                                    click.prompt("请输入DNS：", default="114.114.114.114 8.8.8.8"))
            elif user_c_str == "3":
                change_interface_ip(interface_list[name_input_str],
                                    com_ip_list[0],
                                    com_ip_list[1],
                                    com_ip_list[2],
                                    com_ip_list[3])

    else:
        print("输入错误，请从新输入： ")
