import os
from flask import Flask, request, render_template, session, redirect, url_for, flash, make_response
from flask_script import Manager, Shell
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, SubmitField, PasswordField, SelectField, FileField, BooleanField, TextAreaField, ValidationError
from wtforms.validators import Required, Length, Email, Regexp, EqualTo, Optional
from flask_sqlalchemy import SQLAlchemy
import random

from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, login_required, logout_user, login_user, UserMixin, current_user


from flask_mail import Mail, Message
from threading import Thread
from flask_migrate import Migrate, MigrateCommand

import petl as etl
import requests
import json
from bs4 import BeautifulSoup

import unittest

# Configure base directory of app
basedir = os.path.abspath(os.path.dirname(__file__))
database_password = os.environ.get('DATABASE_PASSWORD')


#Application configurations
app = Flask(__name__)

app.config['HEROKU_ON'] = os.environ.get('HEROKU')
app.static_folder = 'static'
app.config['SECRET_KEY'] = 'asdeomfnbp34t3tsocapmcsd6547djvsnosni45748t4t344nyhhh6555'
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get('DATABASE_URL') or "postgresql://postgres:"+database_password+"@localhost:5432/Final_Project"
# Lines for db setup so it will work as expected
app.config['SQLALCHEMY_COMMIT_ON_TEARDOWN'] = True
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

#Email configuration specifications
app.config['MAIL_SERVER'] = 'smtp.googlemail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['FLASKY_ADMIN'] = os.environ.get('FLASKY_ADMIN')
app.config['FLASKY_MAIL_SUBJECT_PREFIX'] = '[Flasky]'
app.config['FLASKY_MAIL_SENDER'] = os.environ.get('FLASKY_ADMIN')


# Set up Flask debug and necessary additions to app
manager = Manager(app)
db = SQLAlchemy(app) # For database use
migrate = Migrate(app, db) # For database use/updating
manager.add_command('db', MigrateCommand) # Add migrate command to manager
mail = Mail(app)
#Login configurations setup
login_manager = LoginManager()
login_manager.session_protection = 'strong'
login_manager.login_view = 'login'
login_manager.init_app(app) # set up login manager

## Set up Shell context so it's easy to use the shell to debug
# Define function
def make_shell_context():
    return dict( app=app, db=db, Investor= Investor, Suggestion = Suggestion, Business = Business, Feedback= Feedback)
# Add function use to manager
manager.add_command("shell", Shell(make_context=make_shell_context))

#Functions for sending an email
def send_async_email(app, msg):
    with app.app_context():
        mail.send(msg)

def send_email(to, subject, template, **kwargs):
    msg = Message(app.config['FLASKY_MAIL_SUBJECT_PREFIX'] + subject, sender=app.config['FLASKY_MAIL_SENDER'], recipients=[to])
    msg.body = render_template(template + '.txt', **kwargs)
    msg.html = render_template(template + '.html', **kwargs)
    thr = Thread(target=send_async_email, args=[app, msg])
    thr.start()
    return thr

#Set up association table for many to many between Suggestion and Business
Reference_Guide = db.Table('reference_guide', db.Column('suggestion_id', db.Integer, db.ForeignKey('suggestions.id')),db.Column('business_id', db.Integer, db.ForeignKey('businesses.id')))

#Setting up models
class Investor(UserMixin, db.Model):
	__tablename__ = "investors"
	id = db.Column(db.Integer, primary_key = True)
	username = db.Column(db.String(255), unique=True, index=True)
	profile_image = db.Column(db.LargeBinary)
	email = db.Column(db.String(64), unique=True, index=True)
	#set up for one to many relationship between user(one) and suggestion(many)
	suggestions = db.relationship("Suggestion", backref ="Investor")
	password_hash = db.Column(db.String(128))

	@property
	def password(self):
		raise AttributeError('Apparently your password is locked in another castle')

	@password.setter
	def password(self, password):
		self.password_hash = generate_password_hash(password)

	def verify_password(self, password):
		return check_password_hash(self.password_hash, password)

	@property
	def is_authenticated(self):
		return True
	@property
	def is_active(self):
		return True

class Suggestion(db.Model):
	__tablename__ = "suggestions"
	id = db.Column(db.Integer, primary_key=True)
	investor_id = db.Column(db.Integer, db.ForeignKey("investors.id")) 
	businesses = db.relationship('Business',secondary=Reference_Guide,backref = db.backref('suggestions', lazy ='dynamic'), lazy='dynamic')
	#suggestion_content must be in "company|numb|link|,company2|numb2|link2" format for later parsing steps
	suggestion_content= db.Column(db.Text)

class Business(db.Model):
	__tablename__ = "businesses"
	id = db.Column(db.Integer, primary_key=True)
	company_name= db.Column(db.Text)
	ticker_symbol= db.Column(db.Text)
	industry=db.Column(db.Text)
	link_to_comp_info = db.Column(db.Text)

class Feedback(db.Model):
	__tablename__ = "feedback"
	id = db.Column(db.Integer, primary_key=True)
	investor_id = db.Column(db.Integer, db.ForeignKey("investors.id"))
	feedback = db.Column(db.Text)
	satisfaction = db.Column(db.String(6))
# DB load functions
@login_manager.user_loader
def load_user(investor_id):
	return Investor.query.get(int(investor_id))

#Setting up Forms
class New_Investor_RegistrationForm(FlaskForm):
    email = StringField('Email:', validators=[Required(),Length(1,64),Email()])
    username = StringField('Username:',validators=[Required(),Length(1,64),Regexp('^[A-Za-z][A-Za-z0-9_.]*$',0,'Usernames must have only letters, numbers, dots or underscores')])
    profile_pic= FileField("Give us a picture for your profile:Upload a .jpg, .png, or a gif file!")
    password = PasswordField('Password:',validators=[Required(),EqualTo('password2',message="This one is not like the other")])
    password2 = PasswordField("Confirm Password:",validators=[Required()])
    submit = SubmitField('Join Your Fellow Investors')

    def validate_email(self,field):
        if Investor.query.filter_by(email=field.data).first():
            raise ValidationError('That email is already registered!')

    def validate_username(self,field):
        if Investor.query.filter_by(username=field.data).first():
            raise ValidationError('Seems like another person liked that username too, try another!')

class Investor_LoginForm(FlaskForm):
    email = StringField('Email', validators=[Required(), Length(1,64), Email()])
    password = PasswordField('Password', validators=[Required()])
    remember_me = BooleanField('Keep me logged in')
    submit = SubmitField('Log In')

class Suggestion_RequestForm(FlaskForm):
	State = SelectField('What state do you live in?', choices=[('alabama','alabama'),('alaska','alaska'),('arizona','arizona'),('arkansas','arkansas'),('california','california'),
		('colorado','colorado'),('connecticut','connecticut'),('delaware','delaware'),('florida','florida'),('georgia','georgia'),('hawaii','hawaii'),('idaho','idaho'),
		('illinois','illinois'),('indiana','indiana'),('iowa','iowa'),('kansas','kansas'),('kentucky','kentucky'),('louisiana','louisiana'),('maine','maine'),('maryland','maryland'),
		('massachusetts','massachusetts'),('michigan','michigan'),('minnesota','minnesota'),('mississippi','mississippi'),('missouri','missouri'),('montana', 'montana'),('nebraska','nebraska'),
		('nevada','nevada'),('new hampshire','new hampshire'),('new jersey','new jersey'),('new mexico','new mexico'),('new york','new york'),('north carolina','north carolina'),
		('north dakota','north dakota'),('ohio','ohio'),('oklahoma','oklahoma'),('oregon','oregon'),('pennsylvania','pennsylvania'),('rhode island','rhode island'),('south carolina','south carolina'),
		('south dakota','south dakota'),('tennessee','tennessee'),('texas','texas'),('utah','utah'),('vermont','vermont'),('virginia','virginia'),('washington','washington'),('west virginia','west virginia'),
		('wisconsin','wisconsin'),('wyoming','wyoming'),('district of columbia','district of columbia'), ('puerto rico','puerto rico')])
	New_Data_Request = SelectField('Would you like to request today\'s data?', choices=[('yes','yes'),('no','no')], validators = [Required()]) 
	#Email_Request = SelectField('Would you like to be emailed a copy?', choices=[('yes','yes'),('no','no')], validators = [Required()])
	submit = SubmitField('Get Your Suggestions!')

class FeedbackForm(FlaskForm):
	Satisfaction = SelectField('Are you satisfied with your experience?', choices=[('yes','yes'),('no','no')], validators = [Required()])
	Feedback =TextAreaField("Got any suggestions, comments, concerns, let us know!", validators = [Required()])
	company_name = StringField("Enter the name of a Business you'd like to add.", validators =[Optional()])
	ticker_symbol = StringField("Enter the ticker symbol of the business you'd like to add.",validators =[Optional()])
	industry =StringField("Enter the industry that this business is associated with.",validators = [Optional()])
	link_to_comp_info =StringField("Enter a link that we can use to give your fellow investors a chance to learn more.", validators = [Optional()])
	submit = SubmitField('Send Your Feedback')


#App Routes

@app.route('/')
def Home_Page():
	extra_info =[("https://www.cnbc.com/id/100450613", 'CNBC-How many stocks should you own at one time?'),
				 ("https://www.thestreet.com/story/13588155/1/this-is-why-how-many-shares-matters.html", 'TheStreet-How many shares should I buy?'),
				 ("https://www.gobankingrates.com/investing/10-stocks-beginners-try-2016/",'GoBankingRates-10 Stocks for Beginners to Try in 2017'),
				 ("https://www.gobankingrates.com/investing/9-safe-stocks-first-time-investors/", 'GoBankingRates-9 Safe Stocks for First-Time Investors'),
				 ("http://www.investopedia.com/articles/pf/07/budget-qs.asp?lgl=myfinance-layout-no-ads",'Investopedia-How much should I set aside for investments?'),
				 ("http://finance.zacks.com/percentage-should-set-stop-loss-investing-stock-market-4421.html", 'Zacks Finance-Stop Losses and where to set them')]
	#Will show a homepage that explains what the app is supposed to do, as well as
	#provide links with information related to the companies. Another link will 
	#direct the user to the actual form
	return render_template('Home_Page_Design.html', extra_info = extra_info)

@app.route('/Investor_Login', methods=["GET","POST"])#Login Page
def Investor_Login():
	form = Investor_LoginForm()
	if form.validate_on_submit():
		investor = Investor.query.filter_by(email=form.email.data).first()
		if investor is not None and investor.verify_password(form.password.data):
			login_user(investor, form.remember_me.data)
			return redirect(request.args.get('next') or url_for('Investment_App_Form'))
		flash("We don't have that username or password in our records!")
	return render_template('Investor_Login.html', form=form)

@app.route('/investor_profile_image')
@login_required
def investor_profile_image():
    return app.response_class(current_user.profile_image, mimetype='application/octet-stream')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You've Been Logged Out\nHave A Good One, Come Back Soon")
    return redirect(url_for('Home_Page'))

@app.route('/Join_Fellow_Investors',methods=["GET","POST"])#new user Registration
def join_fellow_users():
	form = New_Investor_RegistrationForm()
	if form.validate_on_submit():
		investor = Investor(email=form.email.data,username=form.username.data,password=form.password.data, profile_image=form.profile_pic.data.read())
		db.session.add(investor)
		db.session.commit()
		flash("Welcome to the Investor's Handbook! You can now log in!")
		return redirect(url_for('Investor_Login'))
	flash("There was an error with your login")
	return render_template('Join_Fellow_Investors.html', form=form)

@app.route('/User_Homepage', methods=["GET","POST"]) #Contains Suggestion request form
@login_required
def Investment_App_Form():
	#Will show the WTForm asking for state and whether they'd like to update the information
	#on file. The cookie will hold the information related to whether they'd like to update

	investor_name = current_user.username
	investor_profile_image = current_user.profile_image
	Suggestion_Request_Form = Suggestion_RequestForm()
	#return render_template('Users_State_Form.html', form = Users_State_Form)
	newdata_response= make_response(render_template('Suggestion_Request_Form.html', form = Suggestion_Request_Form, investor_name = current_user.username, investor_profile_image = current_user.profile_image))
	newdata_response.set_cookie('data_requested', 'no')
	return newdata_response


@app.route('/User_Investment_Suggestions', methods = ['GET', 'POST'])
@login_required
def Investment_App_Suggestions():
	#Uses cookie and requests to figure out suggestions and then shows them
	CACHE_FNAME = "Investment_App_Data.json"
	Company_Total_Info = []
	Investment_App_Suggestions_results = []
	Did_we_update = ''
	HardCoded_Companies = [('Verizon', 'VZ', 'Communications','https://en.wikipedia.org/wiki/Verizon_Communications'),('Chevron Corp.', 'CVX', 'Energy','https://en.wikipedia.org/wiki/Chevron_Corporation'),('Caterpillar Inc.', 'CAT', 'Construction','https://en.wikipedia.org/wiki/Caterpillar_Inc.'),
				 ('International Business Machines Corp.', 'IBM', 'Technology','https://en.wikipedia.org/wiki/IBM'),('ExxonMobil Corp.','XOM', 'Energy','https://en.wikipedia.org/wiki/ExxonMobil'),
				 ('Pfizer Inc.','PFE', 'Medicine','https://en.wikipedia.org/wiki/Pfizer'),('Merck & Co. Inc.', 'MRK', 'Medicine','https://en.wikipedia.org/wiki/Merck_%26_Co.'),('Proctor & Gamble Co.', 'PG', 'Consumer Goods','https://en.wikipedia.org/wiki/Procter_%26_Gamble'),
				 ('Wal-Mart Stores, Inc.', 'WMT', 'Retail','https://en.wikipedia.org/wiki/Walmart'),('Cisco Systems Inc.', 'CSCO', 'technology','https://en.wikipedia.org/wiki/Cisco_Systems'),
				 ('Microsoft', 'MSFT','Technology','https://en.wikipedia.org/wiki/Microsoft'),('PepsiCo','PEP','Consumer Goods','https://en.wikipedia.org/wiki/PepsiCo'),
				 ('3M', 'MMM','Industrial_Goods','https://en.wikipedia.org/wiki/3M'),('Dover', 'DOV', 'Industrial Goods','https://en.wikipedia.org/wiki/Dover_Corporation'),
				 ('MasterCard','MA','Financial','https://en.wikipedia.org/wiki/MasterCard'),('Starwood Property Trust','STWD','Financial', 'https://en.wikipedia.org/wiki/Starwood_Capital_Group'),
				 ('Apple', 'AAPL', 'Consumer Goods','https://en.wikipedia.org/wiki/Apple_Inc.')]
	
	def get_quandl_data(searchterm):
		base_url ="https://www.quandl.com/api/v3/datasets/WIKI/{}.json?".format(searchterm)
		param_d = {}
		#Dont Forget to take this out and replace with os.environ(API_KEY)
		param_d["api_key"] ="ZwHoW63KRFgak7tG9rGM"

		if searchterm in CACHE_DICTION:
			quandl_data = CACHE_DICTION[searchterm]
			return(quandl_data)
		else:
			quandl_response = requests.get(base_url, params = param_d)
			quandl_data = json.loads(quandl_response.text)
			if "quandl_error" in quandl_data.keys():
				return("nope")
			else:
				CACHE_DICTION[searchterm] = quandl_data
				f = open(CACHE_FNAME, 'w')
				f.write(json.dumps(CACHE_DICTION))
				f.close()
				return(quandl_data)

	def Get_Company_Stock_Info(Stock_Symbol):
		#Insert call to quandl and returns the info I need specifically.
		company_data = get_quandl_data(Stock_Symbol)
		stock_close_recent = company_data["dataset"]["data"][0][4]
		stock_close_dayb4 = company_data["dataset"]["data"][1][4]
		return(int(stock_close_recent),int(stock_close_dayb4))

	def Calculate_amount_to_invest_per_month(state):
		#Gives the amount to be invested per month from the net income
		State_Incomes = {} 
		state_income_tuples = etl.fromcsv('state_incomes.csv')
		for item in state_income_tuples[1:]:
			State_Incomes[item[0]] = int(item[1])

		Max_Money_Risk_per_month_forfive_shares = State_Incomes[state]/60
		return(int(Max_Money_Risk_per_month_forfive_shares))

	def calculate_stop_loss(stock_prices):
		stoploss = stock_prices[0] - stock_prices[1]
		if stoploss == 0:
			stoploss = stock_prices[0]
			return(stoploss)
		elif stoploss < 0:
			stoploss = stock_prices[0]
			return(stoploss)
		else:
			return(stoploss)

	    	#Should return list similar to [['company', 'numb', 'link'], ['company2', 'numb2', 'link2']]
	def calculate_number_of_stocks_to_buy(Investing_Money, stock_prices):
		stoploss = calculate_stop_loss(stock_prices)
		number_of_stocks_bought = int(Investing_Money/stoploss)
		return(number_of_stocks_bought)

	def get_or_create_Business(db_session, company_name, ticker_symbol, industry, link_to_comp_info):
		business = db_session.query(Business).filter_by(ticker_symbol=ticker_symbol).first()
		if business:
			return business
		else:
			company_data = get_quandl_data(ticker_symbol)
			if type(company_data) == type(""):
				return("That's not a valid business!")
			else:
				business = Business(company_name=company_name, ticker_symbol=ticker_symbol, industry = industry, link_to_comp_info=link_to_comp_info)
				db_session.add(business)
				db_session.commit()
				return business

	def get_or_create_suggestion(db_session, current_user, call_type, Company_Total_Info_Sorted=[], Investing_Money=0, suggestions =""):
		if call_type =="create":
			Businesses_in_suggestion=[]
			suggestion_text = ""
			results = []
			for company_info in Company_Total_Info_sorted[:9]:
				#appends to a list name of company, number of stocks bought, current price, industry, link
				company = company_info[0]
				number_of_stocks_bought = calculate_number_of_stocks_to_buy(Investing_Money,company_info[1])
				current_price = company_info[1][0]
				industry =  company_info[2]
				link_to_comp_info = company_info[3]
				ticker_symbol= company_info[4]
				results.append((company, number_of_stocks_bought,current_price,industry,link_to_comp_info,ticker_symbol))
				business=get_or_create_Business(db_session,company,ticker_symbol,industry,link_to_comp_info)
				Businesses_in_suggestion.append(business)

				if suggestion_text =="":
					suggestion_text= company+"|"+str(number_of_stocks_bought)+"|"+str(current_price)+"|"+industry+"|"+link_to_comp_info+","
				else:
					suggestion_text = suggestion_text+company+"|"+str(number_of_stocks_bought)+"|"+str(current_price)+"|"+industry+"|"+link_to_comp_info+","
			#suggestion_text= suggestion_text+"-"
			suggestion = Suggestion(investor_id=current_user, suggestion_content=suggestion_text)
			for business in Businesses_in_suggestion:
				suggestion.businesses.append(business)
			db_session.add(suggestion)
			db_session.commit()
			return results
		elif call_type == "get":
			suggestion_list =[]
			company = suggestions.split(',')
			for info in company:
				suggestion_list.append(info.split('|'))
			return suggestion_list
	
	form = Suggestion_RequestForm(request.form)
	if request.method == 'POST' and form.validate_on_submit():
		State = form.State.data
		Are_we_updating = form.New_Data_Request.data
		if Are_we_updating == '':
			Are_we_updating = request.cookies.get('data_requested')

		#print(Are_we_updating)
		#cache_creation(Are_we_updating)
		if Are_we_updating == 'no':
			try:
				cache_file = open(CACHE_FNAME,'r')
				cache_contents = cache_file.read()
				cache_file.close()
				CACHE_DICTION = json.loads(cache_contents)
				Did_we_update ='No'
			except:
				CACHE_DICTION = {}
				Did_we_update ='HadTo'
		else:
			CACHE_DICTION = {}
			Did_we_update = 'Yes'

		for company in HardCoded_Companies:
			#company name, company stock symbol, industry, link, 
			get_or_create_Business(db.session, company[0], company[1], company[2], company[3])
	
		Companies = Business.query.all()
		for	company in Companies:
			Company_Total_Info.append((company.company_name,Get_Company_Stock_Info(company.ticker_symbol),company.industry,company.link_to_comp_info,company.ticker_symbol))
		Investing_Money = Calculate_amount_to_invest_per_month(State)
		#roughly middle ground value
		if Investing_Money >= 967:
			Company_Total_Info_sorted = sorted(Company_Total_Info, key = lambda x: x[1][0], reverse = True)
		else:
			Company_Total_Info_sorted = sorted(Company_Total_Info, key = lambda x: x[1][0])
		print(Company_Total_Info_sorted)
		Investment_App_Suggestions_results = get_or_create_suggestion(db_session = db.session, current_user=current_user.id, call_type ='create', Company_Total_Info_Sorted = Company_Total_Info_sorted, Investing_Money = Investing_Money)	
		return(render_template('Investment_Suggestions.html', result = (Investment_App_Suggestions_results, Did_we_update)))
	flash('All fields required and All entries must be lowercase!')
	return(redirect(url_for('Investment_App_Form')))

@app.route('/Suggestion_History') #Shows a user's previous suggestions
@login_required
def suggestion_history():
	all_suggestions = []

	def get_or_create_suggestion(db_session, current_user, call_type, Company_Total_Info_Sorted=[], Investing_Money=0, suggestions =""):
		if call_type =="create":
			Businesses_in_suggestion=[]
			suggestion_text = ""
			results = []
			for company_info in Company_Total_Info_sorted[:9]:
				#appends to a list name of company, number of stocks bought, current price, industry, link
				company = company_info[0]
				number_of_stocks_bought = calculate_number_of_stocks_to_buy(Investing_Money,company_info[1])
				current_price = company_info[1][0]
				industry =  company_info[2]
				link_to_comp_info = company_info[3]
				ticker_symbol= company_info[4]
				results.append((company, number_of_stocks_bought,current_price,industry,link_to_comp_info,ticker_symbol))
				business=get_or_create_Business(db_session,company,ticker_symbol,industry,link_to_comp_info)
				Businesses_in_suggestion.append(business)

				if suggestion_text =="":
					suggestion_text= company+"|"+str(number_of_stocks_bought)+"|"+str(current_price)+"|"+industry+"|"+link_to_comp_info+","
				else:
					suggestion_text = suggestion_text+company+"|"+str(number_of_stocks_bought)+"|"+str(current_price)+"|"+industry+"|"+link_to_comp_info+","
			#suggestion_text= suggestion_text+"-"
			suggestion = Suggestion(investor_id=current_user, suggestion_content=suggestion_text)
			for business in Businesses_in_suggestion:
				suggestion.businesses.append(business)
			db_session.add(suggestion)
			db_session.commit()
			return results
		elif call_type == "get":
			suggestion_list =[]
			company = suggestions.split(',')
			for info in company:
				suggestion_list.append(info.split('|'))
			return suggestion_list

	investors_suggestions = current_user.suggestions 
	#Suggestion.filter_by(investor_id = current_user.id).all()
	for suggestion in investors_suggestions:
		all_suggestions.append(get_or_create_suggestion(db.session, current_user.id, 'get', suggestions=suggestion.suggestion_content))
	return(render_template('Suggestion_History.html', all_suggestions = all_suggestions))

@app.route('/Help_Make_Our_App_Better', methods=["GET","POST"])#Feedback page
@login_required
def feedback():
	def get_quandl_data(searchterm):
		base_url ="https://www.quandl.com/api/v3/datasets/WIKI/{}.json?".format(searchterm)
		param_d = {}
		#Dont Forget to take this out and replace with os.environ(API_KEY)
		param_d["api_key"] ="ZwHoW63KRFgak7tG9rGM"

		if searchterm in CACHE_DICTION:
			quandl_data = CACHE_DICTION[searchterm]
			return(quandl_data)
		else:
			quandl_response = requests.get(base_url, params = param_d)
			quandl_data = json.loads(quandl_response.text)
			if "quandl_error" in quandl_data.keys():
				return("nope")
			else:
				CACHE_DICTION[searchterm] = quandl_data
				f = open(CACHE_FNAME, 'w')
				f.write(json.dumps(CACHE_DICTION))
				f.close()
				return(quandl_data)

	def get_or_create_Business(db_session, company_name, ticker_symbol, industry, link_to_comp_info):
		business = db_session.query(Business).filter_by(ticker_symbol=ticker_symbol).first()
		if business:
			return business
		else:
			company_data = get_quandl_data(ticker_symbol)
			if type(company_data) == type(""):
				return("That's not a valid business!")
			else:
				business = Business(company_name=company_name, ticker_symbol=ticker_symbol, industry = industry, link_to_comp_info=link_to_comp_info)
				db_session.add(business)
				db_session.commit()
				return business

	CACHE_FNAME = "Investment_App_Data.json"
	form = FeedbackForm()
	if form.validate_on_submit():
		feedback = Feedback(investor_id=current_user.id, satisfaction=form.Satisfaction.data, feedback=form.Feedback.data)
		db.session.add(feedback)
		db.session.commit()
		send_email(app.config['FLASKY_ADMIN'], 'Feedback Submitted','feedback_submission', feedback=feedback)
		try:
			cache_file = open(CACHE_FNAME,'r')
			cache_contents = cache_file.read()
			cache_file.close()
			CACHE_DICTION = json.loads(cache_contents)
		except:
			CACHE_DICTION = {}
			Did_we_update ='HadTo'
		get_or_create_Business(db.session, form.company_name.data, form.ticker_symbol.data, form.industry.data, form.link_to_comp_info.data)
		flash("Thanks For Your Feedback")
		return redirect(url_for('Investment_App_Form'))
	return render_template('Feedback.html', form=form)


@app.route('/Business_Data_At_Your_Fingertips', methods=["GET","POST"])# shows available businesses, but also acts as a way to market
@login_required
def available_businesses():
	available_businesses = []
	businesses= Business.query.all()
	for business in businesses:
		available_businesses.append((business.company_name,business.ticker_symbol, business.industry,business.link_to_comp_info))
	return render_template('Available_Businesses.html', available_businesses = available_businesses )

@app.route('/the_perks', methods=["GET","POST"])# shows available businesses, but also acts as a way to market
def the_perks():
	available_businesses = []
	businesses= Business.query.limit(5)
	for business in businesses:
		available_businesses.append((business.company_name,business.ticker_symbol, business.industry,business.link_to_comp_info))

	return render_template('The_Perks.html', available_businesses = available_businesses)

@app.errorhandler(404)
def page_not_found(e):
	return render_template('404.html'), 404

@app.errorhandler(500)
def Internal_Server_Error(e):
	extra_info =[("https://www.cnbc.com/id/100450613", 'CNBC-How many stocks should you own at one time?'),
				 ("https://www.thestreet.com/story/13588155/1/this-is-why-how-many-shares-matters.html", 'TheStreet-How many shares should I buy?'),
				 ("https://www.gobankingrates.com/investing/10-stocks-beginners-try-2016/",'GoBankingRates-10 Stocks for Beginners to Try in 2017'),
				 ("https://www.gobankingrates.com/investing/9-safe-stocks-first-time-investors/", 'GoBankingRates-9 Safe Stocks for First-Time Investors'),
				 ("http://www.investopedia.com/articles/pf/07/budget-qs.asp?lgl=myfinance-layout-no-ads",'Investopedia-How much should I set aside for investments?'),
				 ("http://finance.zacks.com/percentage-should-set-stop-loss-investing-stock-market-4421.html", 'Zacks Finance-Stop Losses and where to set them')]
	return render_template('500.html',extra_info = extra_info), 500


#I attempted to do unittests but had trouble figuring out how to run them, even after googling and looking at the book, so I could check that they worked
# I don't want to jeapordize the rest of the code.

# class Flask_Tester(unittest.TestCase):
# 	def setup(self):
# 		self.app= create_app('testing')
# 		self.app_context = self.app.app_context()
# 		self.app_context.push()
# 		db.create_all()
# 		Role.insert_roles()
# 		self.client = self.app.test_client(use_cookies=True)

# 	def tearDown(self):
# 		db.session.remove()
# 		db.drop_all()
# 		self.app_context.pop()

# 	def test_home_page(self):#Checking thatr the HomePage works
# 		response = self.client.get(url_for('Home_Page'))
# 		self.assertTrue("Investor's Handbook" in response.get_data(as_text=True))
	
# 	def test_get_suggestion(self):
# 		def get_or_create_suggestion(db_session, current_user, call_type, Company_Total_Info_Sorted=[], Investing_Money=0, suggestions =""):
# 			if call_type =="create":
# 				Businesses_in_suggestion=[]
# 				suggestion_text = ""
# 				results = []
# 				for company_info in Company_Total_Info_sorted[:9]:
# 					#appends to a list name of company, number of stocks bought, current price, industry, link
# 					company = company_info[0]
# 					number_of_stocks_bought = calculate_number_of_stocks_to_buy(Investing_Money,company_info[1])
# 					current_price = company_info[1][0]
# 					industry =  company_info[2]
# 					link_to_comp_info = company_info[3]
# 					ticker_symbol= company_info[4]
# 					results.append((company, number_of_stocks_bought,current_price,industry,link_to_comp_info,ticker_symbol))
# 					business=get_or_create_Business(db_session,company,ticker_symbol,industry,link_to_comp_info)
# 					Businesses_in_suggestion.append(business)

# 					if suggestion_text =="":
# 						suggestion_text= company+"|"+str(number_of_stocks_bought)+"|"+str(current_price)+"|"+industry+"|"+link_to_comp_info+","
# 					else:
# 						suggestion_text = suggestion_text+company+"|"+str(number_of_stocks_bought)+"|"+str(current_price)+"|"+industry+"|"+link_to_comp_info+","
# 				#suggestion_text= suggestion_text+"-"
# 				suggestion = Suggestion(investor_id=current_user, suggestion_content=suggestion_text)
# 				for business in Businesses_in_suggestion:
# 					suggestion.businesses.append(business)
# 				db_session.add(suggestion)
# 				db_session.commit()
# 				return results
# 			elif call_type == "get":
# 				suggestion_list =[]
# 				company = suggestions.split(',')
# 				for info in company:
# 					suggestion_list.append(info.split('|'))
# 				return suggestion_list
# 		self.assertEqual(str(get_or_create_suggestion(db.session, current_user.id, 'get', suggestions='company1|info2|info3,company2|info2|info3')),str([['company1','info2','info3'],['company2','info2','info3']]))
# 	def test_quandl(self):
# 		def get_quandl_data(searchterm):
# 			base_url ="https://www.quandl.com/api/v3/datasets/WIKI/{}.json?".format(searchterm)
# 			param_d = {}
# 			#Dont Forget to take this out and replace with os.environ(API_KEY)
# 			param_d["api_key"] ="ZwHoW63KRFgak7tG9rGM"
# 			CACHE_DICTION={}
# 			if searchterm in CACHE_DICTION:
# 				quandl_data = CACHE_DICTION[searchterm]
# 				return(quandl_data)
# 			else:
# 				quandl_response = requests.get(base_url, params = param_d)
# 				quandl_data = json.loads(quandl_response.text)
# 				if "quandl_error" in quandl_data.keys():
# 					return("nope")
# 				else:
# 					CACHE_DICTION[searchterm] = quandl_data
# 					f = open(CACHE_FNAME, 'w')
# 					f.write(json.dumps(CACHE_DICTION))
# 					f.close()
# 					return(quandl_data)
# 		quandl_data = get_quandl_data('JfgLnnj')
# 		self.assertTrue("nope" in quandl_data)

# 	def test_business_model(self):
# 		def get_quandl_data(searchterm):
# 			base_url ="https://www.quandl.com/api/v3/datasets/WIKI/{}.json?".format(searchterm)
# 			param_d = {}
# 			#Dont Forget to take this out and replace with os.environ(API_KEY)
# 			param_d["api_key"] ="ZwHoW63KRFgak7tG9rGM"
# 			CACHE_DICTION={}
# 			if searchterm in CACHE_DICTION:
# 				quandl_data = CACHE_DICTION[searchterm]
# 				return(quandl_data)
# 			else:
# 				quandl_response = requests.get(base_url, params = param_d)
# 				quandl_data = json.loads(quandl_response.text)
# 				if "quandl_error" in quandl_data.keys():
# 					return("nope")
# 				else:
# 					CACHE_DICTION[searchterm] = quandl_data
# 					f = open(CACHE_FNAME, 'w')
# 					f.write(json.dumps(CACHE_DICTION))
# 					f.close()
# 					return(quandl_data)
		
# 		def get_or_create_Business(db_session, company_name, ticker_symbol, industry, link_to_comp_info):
# 			#business = db_session.query(Business).filter_by(ticker_symbol=ticker_symbol).first()
# 			business = None
# 			if business:
# 				return business
# 			else:
# 				company_data = get_quandl_data(ticker_symbol)
# 				if type(company_data) == type(""):
# 					return("That's not a valid business!")
# 				else:
# 					business = Business(company_name=company_name, ticker_symbol=ticker_symbol, industry = industry, link_to_comp_info=link_to_comp_info)
# 					# db_session.add(business)
# 					# db_session.commit()
# 					return business
# 		business= get_or_create_Business('db.session','Netflix','NFLX','Entertainment',link_to_comp_info='https://en.wikipedia.org/wiki/Netflix')
# 		self.assertEqual(business.company_name, 'Netflix')



if __name__== '__main__':
	db.create_all()
	manager.run()