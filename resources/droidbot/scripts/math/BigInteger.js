/**
 * Created by maomao on 2020/4/23.
 */
Java.perform(function() {
    var cn = "java.math.BigInteger";
    var target = Java.use(cn);
    if (target) {
        target.divideAndRemainder.implementation = function(dest) {
            var myArray=new Array()
            myArray[0] = "INTERESTED"  //INTERESTED & SENSITIVE
            myArray[1] = cn + "." + "divideAndRemainder";
            myArray[2] = Java.use("android.util.Log").getStackTraceString(Java.use("java.lang.Exception").$new()).split('\n\tat');
            send(myArray);
            return this.divideAndRemainder.apply(this, arguments);
        };
    }
});