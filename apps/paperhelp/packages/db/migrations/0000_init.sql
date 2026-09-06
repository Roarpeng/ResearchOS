-- PaperHelp initial schema (ADD §11)
CREATE TABLE `documents` (
	`id` text PRIMARY KEY NOT NULL,
	`title` text NOT NULL,
	`created_at` integer NOT NULL,
	`updated_at` integer NOT NULL
);

CREATE TABLE `blocks` (
	`id` text PRIMARY KEY NOT NULL,
	`document_id` text NOT NULL,
	`type` text NOT NULL,
	`content` text NOT NULL,
	`position` integer NOT NULL,
	FOREIGN KEY (`document_id`) REFERENCES `documents`(`id`) ON UPDATE no action ON DELETE cascade
);

CREATE TABLE `figures` (
	`id` text PRIMARY KEY NOT NULL,
	`document_id` text NOT NULL,
	`layout` text NOT NULL,
	`metadata` text NOT NULL,
	FOREIGN KEY (`document_id`) REFERENCES `documents`(`id`) ON UPDATE no action ON DELETE cascade
);

CREATE TABLE `assets` (
	`id` text PRIMARY KEY NOT NULL,
	`path` text NOT NULL,
	`hash` text NOT NULL,
	`width` integer NOT NULL,
	`height` integer NOT NULL
);

CREATE TABLE `citations` (
	`id` text PRIMARY KEY NOT NULL,
	`doi` text,
	`title` text NOT NULL,
	`authors` text NOT NULL,
	`journal` text
);

CREATE TABLE `history` (
	`id` text PRIMARY KEY NOT NULL,
	`action` text NOT NULL,
	`payload` text NOT NULL,
	`created_at` integer NOT NULL
);
