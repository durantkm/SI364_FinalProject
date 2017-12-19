## The Purpose

  I really wanted to create an app that could be a more in-depth tool for people who are not as familiar with investing, which can be used as a good starting point by taking information like income and using a nice sized well of information about different available stocks from a database to give well rounded advice, then emailing this information to the user. The Investor's Handbook is still in early development, but has already shown a lot of promise.

## The Data
	The Investor's Handbook uses market data from the quandl api and a  database used to store information on businesses, as well as users so that the data can be used later to update users when more businesses are available for investment suggestions.
	
	we've also included a state_incomes.csv file which is loaded into the program to provide the income piece for analysis, and so that numbers can be easily updated.

* **There are Four forms a user will see** 
	-- First Form Login Form:
		A user will need to enter a name and password
	--Second Form Create an account:
		A user will need to enter name, password, email, and a image that will act as their profile picture.
	--Third Form Request Suggestion:
		A user will select their state of interest, and whether they'd like to update the database
	--Fourth Feedback Form
		A user will be able to provide our team with feedback through the feedback form(which will email us to let us know), as well as add valid businesses to the database and have immmediate access to that businesses information on their next suggestion request 

* **After a user enters data into the form, what happens? Does that data help a user search for more data? Does that data get saved in a database? Does that determine what already-saved data the user should see?**
	--A user will recieve a tailored sugestion on what stocks to look into and a estimation of how many stocks they could buy. They will also have access to all their previous suggestions for research/comparison purposes. The data will be stored in our database to be accessed later by users. 

##Program Requirements
	For convenience, we have created a requirements.txt file which can be used to install the necessary components.
	For the database you will want to create a database called Final_Project
	* **Additional Settings: You will need to set the following variables as such:** *
		--export DATABASE_PASSWORD = your postgres password(for database use)
		--export MAIL_USERNAME = gmail username(for email)
		--export MAIL_PASSWORD = gmail username(for email)
		--export FLASKY_ADMIN = "Your actual gmail email"


## The Pages

* **How many pages (routes) will your application have?**
	Eleven total pages as of now:
	--Public Pages
		1.Login Page (new)
		2.Page to create a new login(new)
		3.Public Home Page
		4.Interest Page(Marketing Purposes)
	--Login Required Views
		5.User Homepage(Personalized experience per user)
		6.Form(new/updated for final project)
		7.Suggestion Results Page(updated)
		8.Show available Businesses(new)
		9.Show User's suggestions(new)
	--Error Handling Views
		10.500 Error Message for when a entered company doesn't exist
		11.404 Error Message
	
Users who aren't logged in will only be able to visit the pages listed under the public pages, and be prompted to either join(informed of the perks), or asked to login. For Users logged in they will have access to the pages listed under Login Required Views, which work together to live up to the perks we inform people of , as well as contributes to the overall personalized experience for each one of our investor. 

## Extras
Thank You for all your support! It has been a pleasure working on this project, Have a good one!