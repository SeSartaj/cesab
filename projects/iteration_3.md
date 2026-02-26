- projectMember should also have admin role
- when a user creates a project, initially he becomes the admin of this project (a projectMember record is created for him)
- project admin can invite other users to the project. they can write the user's username and search it, and if found can directly invite it. alternatively, they can generate a link which will have a token, and when a non-existing user click on it. they'll be able to register a user and then added to the project. the token will be valid for like a day. my point is that i don't want bots and melicious users to be able to register by themselves. a user to register should have an invitation link. 
- veiwers will be able to view everything. 
- admin will be able to invite user to the project. 
- accountant will be able to do accounting related work. 


- calculate the remaining based on the total contributed. if nothing is contributed yet, then calculate based on commitment. for example, if ahmad have 60% and contributed 600, then the other shareholder or partner, ali, is 400 remaining. 
- when adding to cashbox, filter the cashbox select, so only the cashboxes which have the same currency as transaction currency are displayed. (--)


-there is a bug. when currency is USD, and i choose cashbox which is AFN, then to the cashbox it should be added the changed currency. for example, if cashbox is AFN, and the transaction is in USD, 1000 usd is added at exchange rate of 64, then the cashbox should have 64000 in it. 
- with each cashbox, show its currency as well. 





# Bug fixes and enhacements
- remove direct payment button from vendor detail page. 
- show total amount paid to a vendor 
- when creating a project, automatically creat two cashboxes called (دخل مرکزی - افغانی) and (دخل مرکزی - دالری). 
- 