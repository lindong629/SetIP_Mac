#!/usr/local/bin/python3
# -*- coding: utf-8 -*- 
# Jimmy Lin
import tools_change_ip

while True:

    # 显示菜单
    tools_change_ip.show_menu()

    action = input("请选择操作功能： ")

    # 根据用户选择决定后续操作。 1、查看网卡信息，0、退出系统
    if action == "1":
        tools_change_ip.show_interface_list()

    elif action == "0":
        print("欢迎再次使用【IP管理系统】")
        break

    else:
        print("输入错误，请重新选择")