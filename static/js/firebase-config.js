const firebaseConfig = {
     apiKey: "AIzaSyCQSIutjzaHqcazKtN0dGBpsajHbkvEY2k",
     authDomain: "dispenza-cb47a.firebaseapp.com",
     databaseURL: "https://dispenza-cb47a-default-rtdb.europe-west1.firebasedatabase.app",
     projectId: "dispenza-cb47a",
     storageBucket: "dispenza-cb47a.firebasestorage.app",
     messagingSenderId: "1001679495099",
     appId: "1:1001679495099:web:81df66addfa6979b4dae9e",
     measurementId: "G-88J0WL3EXB"
};

firebase.initializeApp(firebaseConfig);
const auth = firebase.auth();
const db = firebase.firestore();