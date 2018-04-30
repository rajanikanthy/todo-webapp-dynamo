drop table if exists users;
create table users (
    id integer primary key autoincrement,
    username text not null,
    password text not null,
    email_addr text not null
);
drop table if exists tasks;
create table tasks (
    id integer primary key autoincrement,
    user_id integer,
    title text not null,
    description text not null,
    created_date numeric,
    completed_date numeric,
    foreign key(user_id) references users(id)
);