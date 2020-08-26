eff.columns = ['worker_id', 'project_id', 'product_id', 'date', 'output']


#############
if (len(order.columns) == 12):
        #order.columns = ["change_date","create_date","days","delivery_date","delivery_quan","order_id","product_id","product_name","project_id","project_name","quantity","total_output"]
        order.columns = ['order_id', 'project_id', 'project_name', 'product_id', 'product_name', 'delivery_quantity', 'delivery_date', 'total_output', 'quantity', 'days', 'create_date', 'change_date']
elif (len(order.columns) == 13):
        #order.columns = ["change_date","checked","create_date","days","delivery_date","delivery_quan","order_id","product_id","product_name","project_id","project_name","quantity","total_output"]
        order.columns = ['order_id', 'project_id', 'project_name', 'product_id', 'product_name', 'delivery_quantity', 'delivery_date', 'total_output', 'quantity', 'days', 'create_date', 'change_date', 'checked']
else:
        pass
order = order.dropna(axis = 0, how = "any") #防止出现df中有nan


###########
procedure.columns = ["product_id","project_id","step","limit"]


###############
team = pd.DataFrame(data["team"])
team = pd.DataFrame(team,index = list(map(int,np.linspace(0,len(team),len(team),endpoint = False).tolist())))
team.columns = ["team_id","member","product_id","project_id","output"]