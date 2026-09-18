const { MongoClient } = require('mongodb');
const fs = require('fs');
const path = require('path');

const uri = 'mongodb://localhost:27017/bidding_system';
const backupDir = 'C:\\backup\\bidding_system-v1.0-2026-09-18';

async function backupDatabase() {
  const client = new MongoClient(uri);
  
  try {
    await client.connect();
    const db = client.db('bidding_system');
    
    if (!fs.existsSync(backupDir)) {
      fs.mkdirSync(backupDir, { recursive: true });
    }
    
    const collections = await db.listCollections().toArray();
    console.log('Backing up ' + collections.length + ' collections...');
    
    for (const collInfo of collections) {
      const collName = collInfo.name;
      const collection = db.collection(collName);
      const docs = await collection.find({}).toArray();
      
      const filePath = path.join(backupDir, collName + '.json');
      fs.writeFileSync(filePath, JSON.stringify(docs, null, 2), 'utf8');
      
      console.log('OK ' + collName + ': ' + docs.length + ' documents exported');
    }
    
    console.log('\nOK Backup complete: ' + backupDir);
  } catch (error) {
    console.error('ERROR Backup failed:', error.message);
  } finally {
    await client.close();
  }
}

backupDatabase();
