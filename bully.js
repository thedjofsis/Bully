const zerorpc = require('zerorpc');
const fs = require('fs');
const sleep = require('sleep');
const promiseFinally = require('promise.prototype.finally');
//nvm use v8.11.2

promiseFinally.shim();

class State {
	constructor() {
		//State of the node
		// [Down, Election, Reorganization, Normal]
		this.state = 'Normal';
		// coordinator of the node (if coordinator, has it's own id. Otherwise the id of the coordinator node)
		this.coord = 0;
		// The node which recently made this node halt (election started by a higher priority node)
		this.halt = -1;
		// list of nodes which this node believes to be in operation
		this.Up = [];
	}
}

var Bully = new Object(); //Create a new Bully Object
Bully.S = new State(); //assign a new State Object to Bully.S
Bully.S.state = 'Normal'; //set Bully.S.state to Normal (redundant)

Bully.checkServerPool = null; //empty pool

const address = process.argv[2]; //get server + port
Bully.addr = address; //assign it
Bully.config_file = 'server_config_local'; //confile file name

Bully.servers = []; //empty array of servers
Bully.serverListBackup = [];

//read config_file, put the content to an array, trim it and sort it
let f = fs.readFileSync(Bully.config_file, 'utf8').trim().split('\n').sort();
Bully.servers = f.slice(); //f is assigned to Bully.servers
console.log(`My addr: ${Bully.addr}`);
console.log(`Server list: ${Bully.servers}`);

Bully.connections = []; //empty Bully.connections Array

// Assigning priority varirable based on the order in the list
for (let i = 0; i < Bully.servers.length; i++) {
	if (Bully.servers[i] == Bully.addr) { // if the server in the list is the one my script is running...
		Bully.priority = i; //assign i to its priority
		Bully.connections.push(Bully); //push it to the connections array
	} else { //else
		let options = {
			timeout: 1,
		};
		let c = new zerorpc.Client(options); // create new client which will communicate with other servers from the list
		c.connect('tcp://' + Bully.servers[i]); //connect it
		// console.log(`Binding server ${Bully.servers[i]}`);
		Bully.connections.push(c); //push new client
		// console.log(c)
	}
}


//Bully Methods
Bully.areYouThere = function(param, reply) { //when areYouThere is called by a client,
	reply(null, true); //return True using ZeroRPC Method
};

Bully.areYouNormal = function(param, reply) {
	if (this.S.state == 'Normal') {
		reply(null, true);
	} else {
		reply(null, false);
	}
};

Bully.halt = function(number, reply) { //When halt is called...
	this.S.state = 'Election'; // we change the state of this server to Election
	this.S.halt = number; //and change this.S.halt to the number given
	reply(null, true);
};

Bully.newCoordinator = function(nb, reply) { //When newCoordinator is called
	console.log('call newCoordinator');
	if (this.S.halt == nb && this.S.state == 'Election') { //if this.S.halt is True and this.S.state is Election
		this.S.coord = nb; // we give this.S.coord the nb given as parameter
		this.S.state = 'Reorganization'; // and change this.S.state to 'Reorganization'
		reply(null, true);
	}
	return;
};

Bully.ready = function(nb, reply) { //When ready is called...
	console.log('call ready');
	if (this.S.coord == nb && this.S.state == 'Reorganization') { //if this.S.coord == nb AND we have reorganization State,
		this.S.state = 'Normal'; //Set the state back to Normal
		reply(null, true);
	}
	return;
};

Bully.syncFuncCall = function(func_name, client_test, param=null) {
	return new Promise((resolve, reject) => {
		client_test.invoke(func_name, param, function(error, res, more) {
			
			if (error) {
				return reject(error);
			} else {
				return resolve(res);
			}

		});
	});
};

Bully.election = function() { // When election is called...
	console.log('Check the states of higher priority nodes');

	let priorityPlusOne = this.priority + 1; // Priority + 1
	let restOfElements = this.servers.slice(priorityPlusOne); //list of elements from priorityPlusOne to the end

	var counter4 = 0;
	var checker = false;
	for (let i = 0; i <= restOfElements.length; i++) {
		this.syncFuncCall('areYouThere', this.connections[priorityPlusOne+i])
			.then((resp) => {
				checker = true;
				if (this.checkServerPool == null) {
					this.S.coord = this.priority + 1 + i; // change this.S.coord to priority +1 + value of index
					this.S.state = 'Normal'; // change state to Normal
					this.checkServerPool = true;
					this.check();                                     // call check()
				}
				return;
			})
			.catch(() => {
				if (i!= restOfElements.length){
					console.log(`${restOfElements[i]} Timeout 1! Server offline, can't choose this as a coordinator`);
				}
			})
			.finally(() => {
				if (counter4==restOfElements.length && !checker){
					console.log('halt all lower priority nodes including this node');
					console.log(`${this.servers[this.priority]}: I halted myself`);
					this.S.state = 'Election';
					console.log(`I am ${this.S.state}`);
					this.S.halt = this.priority;
					this.S.Up = [];
					this.S.Up.push(this);
					this.serverListBackup.push(this.servers[this.priority]);
					var counter = 0;
					for (let j = 0; j <= this.priority; j++) {
						this.syncFuncCall('halt', this.connections[j], this.priority)
							.then(()=>{
								console.log(`Prompt: ${this.servers[j]} server halted successfully`);
								this.S.Up.push(this.connections[j]);
								this.serverListBackup.push(this.servers[j]);
							})
							.catch(()=>{
								if (j != this.priority){
									console.log(`Prompt: ${this.servers[j]} Timeout 2, server not reachable, cannot halt`);
								}
							})
							.finally(() =>{
									if (counter == this.priority) {
										console.log('inform all nodes of new coordinator');
										this.S.coord = this.priority;
										this.S.State = 'Reorganization';
										var counter2 = 0;
										for(let k = 0;k<this.S.Up.length;k++){
											this.syncFuncCall('newCoordinator', this.S.Up[k], this.priority)
												.then(()=>{
													console.log(`Prompt: ${this.serverListBackup[k]} server received new coordinator`);
												})
												.catch(()=>{
													if (this.S.Up[k] != this){
														console.log(`Prompt: ${this.serverListBackup[k]} Timeout 3, server not reachable, election has to be restarted`);
														this.election();
														return;
													} else {
														console.log("Declaring myself as coordinator");
													}
												})
												.finally(() => {
													if (counter2 == this.S.Up.length-1) {
														var counter3 = 0;
														this.S.state = "Normal";
														for(let l=0;l<this.S.Up.length;l++){
															this.syncFuncCall('ready', this.S.Up[l], this.priority)
																.then(()=>{
																	console.log(`Prompt: ${this.serverListBackup[l]} server is ready (not coordinator)`);
																})
																.catch(()=>{
																	if (this.S.Up[l] != this){
																		console.log(`Prompt: ${this.serverListBackup[l]} Timeout 4, server lost connection, election has to be restarted`);
																		this.election();
																		return;
																	} else {
																		console.log("I am ready");
																	}
																})
																.finally(() => {
																	if (counter3==this.S.Up.length-1){
																		this.check();
																	}
																	counter3++;
																});
														}
													}
													counter2++;
												});
										}
									}
								counter++;
							});
					}
				}
				counter4++;
			});
	}
};

Bully.recovery = function() {
	this.S.halt = -1;
	this.election();
};

Bully.check = function() {
	// var checker_from_invoke = true;
	// while (true) {
	setInterval(()=>{
		console.log('My address is ', this.addr);
		// checker_from_invoke = false;
		if (this.S.coord == this.priority) {
			console.log('I am Coordinator');
		} else {
			console.log('I am Normal');
		}
		//console.log('State:', this.S.state, "Priority", this.S.coord)
		if (this.S.state == 'Normal' && this.S.coord == this.priority) {
			for (let i = 0; i < this.servers.length; i++) {
				if (i != this.priority) {
					//console.log('I am working', i);
					// console.log(this.connections[i], i);
					this.syncFuncCall('areYouNormal', this.connections[i])
						.then((answer) => {
							// console.log('I work', answer);
							if(!answer){
								console.log(`${this.servers[i]} this node is not normal! starting election`);
								checker_from_invoke = true;
								this.election();
								return;
							}
						})
						.catch(() => {
							console.log(`${this.servers[i]} Timeout 5! this normal node is unreachable`);
							// checker_from_invoke = true;
						});
				}
			}
		} else if (this.S.state == 'Normal' && this.S.coord != this.priority) {
			console.log('check coordinator\'s state');
			this.syncFuncCall('areYouThere', this.connections[this.S.coord])
				.then(()=>{
					console.log(`Prompt: ${this.servers[this.S.coord]} coordinator is up`);
				})
				.catch(()=>{
					console.log(`Prompt: ${this.servers[this.S.coord]} coordinator down, start election`);
					this.timeout();
				});
		}
	},5000);
	// sleep.sleep(10);
	// }
	
};

Bully.timeout = function() {
	if (this.S.state == 'Normal' || this.S.state == 'Reorganization') {
		this.syncFuncCall('areYouThere', this.connections[this.S.coord])
			.then(()=>{
				console.log(`Prompt: ${this.servers[this.S.coord]} coordinator alive`);
			})
			.catch(()=>{
				console.log(`Prompt: ${this.servers[this.S.coord]} Timeout 6, coordinator down, start election`);
				this.election();
			});
	} else {
		console.log('starting election');
		this.election();
	}
};

Bully.inititialize = function() {
	this.recovery();

};

const s = new zerorpc.Server(Bully);
s.bind('tcp://' + address);
Bully.inititialize();
console.log(`${address} initializing Server`);